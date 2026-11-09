"""Eventos cotidianos: carga manual (HU-009) y registro en lenguaje natural con inteligencia artificial (HU-008)."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.analisis.servicio import marcar_resumenes_desactualizados
from app.database import get_db
from app.ia import cliente as ia
from app.ia.extraccion import InterpretacionFallida, interpretar
from app.models import Evento, Medicion, Usuario, como_utc
from app.sesiones import usuario_actual

router = APIRouter(prefix="/eventos", tags=["Eventos"])

TipoEvento = Literal["comida", "insulina", "actividad_fisica", "sintoma", "otro"]

# Unidades admitidas para cada tipo (diseño metodológico) y cantidades máximas razonables.
UNIDADES = {
    "comida": {"gramos": 2000, "porciones": 20},
    "insulina": {"unidades": 100},
    "actividad_fisica": {"minutos": 600},
    "sintoma": {},
    "otro": {"minutos": 600},
}


class EventoNuevo(BaseModel):
    tipo: TipoEvento
    descripcion: str
    fecha_hora: datetime  # hora local de la persona, por ejemplo "2026-10-31T13:00"
    hora_aproximada: bool = False
    cantidad: float | None = None
    unidad: str | None = None
    # HU-009, criterio 2: si el día no tiene datos, se pide confirmar antes de guardar.
    confirmar_sin_datos: bool = False

    @field_validator("descripcion", mode="before")
    @classmethod
    def descripcion_obligatoria(cls, valor):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError("Este campo es obligatorio.")
        if len(valor.strip()) > 160:
            raise ValueError("La descripción no puede superar los 160 caracteres.")
        return valor.strip()

    @model_validator(mode="after")
    def cantidad_y_unidad(self):
        admitidas = UNIDADES[self.tipo]
        if self.cantidad is None and self.unidad is None:
            return self
        if self.cantidad is None or not self.unidad:
            raise ValueError("Si indicás una cantidad, indicá también su unidad (y viceversa).")
        if self.unidad not in admitidas:
            opciones = ", ".join(admitidas) or "ninguna (este tipo no lleva cantidad)"
            raise ValueError(f"La unidad no corresponde al tipo de evento. Unidades admitidas: {opciones}.")
        if not 0 < self.cantidad <= admitidas[self.unidad]:
            raise ValueError(f"La cantidad debe ser mayor que 0 y no superar {admitidas[self.unidad]} {self.unidad}.")
        return self


class EventoGuardado(BaseModel):
    id_evento: int
    tipo: str
    descripcion: str
    fecha_hora: datetime
    fecha: date  # día local del evento
    hora: str
    hora_aproximada: bool
    cantidad: float | None
    unidad: str | None
    texto_original: str | None


def evento_publico(e: Evento, zona: ZoneInfo) -> EventoGuardado:
    local = como_utc(e.fecha_hora).astimezone(zona)
    return EventoGuardado(
        id_evento=e.id_evento, tipo=e.tipo, descripcion=e.descripcion, fecha_hora=como_utc(e.fecha_hora),
        fecha=local.date(), hora=local.strftime("%H:%M"), hora_aproximada=e.hora_aproximada, cantidad=e.cantidad,
        unidad=e.unidad, texto_original=e.texto_original,
    )


def _limites(fecha: date, zona: ZoneInfo):
    inicio = datetime.combine(fecha, time.min, tzinfo=zona).astimezone(timezone.utc)
    return inicio, datetime.combine(fecha + timedelta(days=1), time.min, tzinfo=zona).astimezone(timezone.utc)


@router.post("", response_model=EventoGuardado, status_code=status.HTTP_201_CREATED)
def crear_evento(datos: EventoNuevo, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    momento = datos.fecha_hora if datos.fecha_hora.tzinfo else datos.fecha_hora.replace(tzinfo=zona)
    momento = momento.astimezone(timezone.utc)

    if not datos.confirmar_sin_datos:
        inicio, fin = _limites(momento.astimezone(zona).date(), zona)
        hay_datos = db.scalar(select(
            exists().where(Medicion.id_usuario == usuario.id_usuario, Medicion.fecha_hora >= inicio, Medicion.fecha_hora < fin)
        )) or db.scalar(select(
            exists().where(Evento.id_usuario == usuario.id_usuario, Evento.estado == "confirmado",
                           Evento.fecha_hora >= inicio, Evento.fecha_hora < fin)
        ))
        if not hay_datos:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Ese día no tiene mediciones ni otros eventos. ¿La fecha es correcta? Podés corregirla o confirmar igual.",
            )

    evento = Evento(
        id_usuario=usuario.id_usuario, fecha_hora=momento, hora_aproximada=datos.hora_aproximada,
        tipo=datos.tipo, descripcion=datos.descripcion, cantidad=datos.cantidad, unidad=datos.unidad,
        estado="confirmado",
    )
    db.add(evento)
    marcar_resumenes_desactualizados(db, usuario, {momento.astimezone(zona).date()})
    db.commit()
    db.refresh(evento)
    return evento_publico(evento, zona)


@router.get("", response_model=list[EventoGuardado])
def eventos_del_dia(
    fecha: date = Query(..., description="Día (AAAA-MM-DD)"),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    inicio, fin = _limites(fecha, zona)
    eventos = db.scalars(
        select(Evento)
        .where(Evento.id_usuario == usuario.id_usuario, Evento.estado == "confirmado",
               Evento.fecha_hora >= inicio, Evento.fecha_hora < fin)
        .order_by(Evento.fecha_hora)
    ).all()
    return [evento_publico(e, zona) for e in eventos]


@router.get("/recientes", response_model=list[EventoGuardado])
def eventos_recientes(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    eventos = db.scalars(
        select(Evento).where(Evento.id_usuario == usuario.id_usuario, Evento.estado == "confirmado")
        .order_by(Evento.fecha_registro.desc()).limit(10)
    ).all()
    return [evento_publico(e, zona) for e in eventos]


@router.delete("/{id_evento}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_evento(id_evento: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    evento = db.scalar(select(Evento).where(Evento.id_evento == id_evento, Evento.id_usuario == usuario.id_usuario))
    if not evento:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El evento no existe.")
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    if evento.estado == "confirmado":
        marcar_resumenes_desactualizados(db, usuario, {como_utc(evento.fecha_hora).astimezone(zona).date()})
    db.delete(evento)
    db.commit()


# Registro en lenguaje natural (HU-008)

class PedidoInterpretacion(BaseModel):
    texto: str
    fecha: date  # día de referencia (el que la persona tiene elegido en pantalla)

    @field_validator("texto", mode="before")
    @classmethod
    def texto_obligatorio(cls, valor):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError("Escribí qué pasó para poder interpretarlo.")
        if len(valor) > 1000:
            raise ValueError("El texto no puede superar los 1000 caracteres.")
        return valor.strip()


class BorradorPublico(EventoGuardado):
    hora_propuesta: bool
    advertencias: list[str]


class Interpretacion(BaseModel):
    texto_original: str
    modelo: str
    borradores: list[BorradorPublico]


class EventoAConfirmar(EventoNuevo):
    id_evento: int


class PedidoConfirmacion(BaseModel):
    eventos: list[EventoAConfirmar]


class PedidoDescarte(BaseModel):
    ids: list[int]


@router.post("/interpretar", response_model=Interpretacion)
def interpretar_texto(datos: PedidoInterpretacion, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Convierte el texto en eventos estructurados con inteligencia artificial (HU-008)."""
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    ahora = datetime.now(zona)
    hora_actual = ahora.time().replace(second=0, microsecond=0) if datos.fecha == ahora.date() else None
    try:
        borradores = interpretar(datos.texto, datos.fecha, hora_actual)
    except ia.ServicioNoDisponible as error:
        # Criterio 5: se conserva lo escrito y se ofrece la carga manual.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"{error} Tu texto se conservó: podés cargar los eventos manualmente.")
    except InterpretacionFallida:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "No se pudo interpretar el texto. Tu texto se conservó: podés cargar los eventos manualmente.")
    if not borradores:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "No se encontraron eventos en el texto. Probá describir qué comiste, qué insulina te aplicaste o qué actividad hiciste.")

    publicos = []
    for b in borradores:
        evento = Evento(
            id_usuario=usuario.id_usuario,
            fecha_hora=b.fecha_hora.replace(tzinfo=zona).astimezone(timezone.utc),
            hora_aproximada=b.hora_aproximada,
            texto_original=datos.texto,
            tipo=b.tipo,
            descripcion=b.descripcion or "Sin descripción",
            cantidad=b.cantidad,
            unidad=b.unidad,
            estado="borrador",
        )
        db.add(evento)
        db.flush()
        publicos.append(BorradorPublico(**evento_publico(evento, zona).model_dump(),
                                        hora_propuesta=b.hora_propuesta, advertencias=b.advertencias))
    db.commit()
    return Interpretacion(texto_original=datos.texto, modelo=ia.modelo(), borradores=publicos)


@router.post("/confirmar", response_model=list[EventoGuardado])
def confirmar_borradores(datos: PedidoConfirmacion, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Confirma los borradores, con las correcciones que haya hecho la persona (HU-008, criterio 4)."""
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    confirmados, fechas = [], set()
    for e in datos.eventos:
        evento = db.scalar(select(Evento).where(
            Evento.id_evento == e.id_evento, Evento.id_usuario == usuario.id_usuario, Evento.estado == "borrador"
        ))
        if not evento:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Uno de los borradores ya no existe o ya fue confirmado.")
        momento = e.fecha_hora if e.fecha_hora.tzinfo else e.fecha_hora.replace(tzinfo=zona)
        evento.fecha_hora = momento.astimezone(timezone.utc)
        evento.tipo, evento.descripcion = e.tipo, e.descripcion
        evento.cantidad, evento.unidad, evento.hora_aproximada = e.cantidad, e.unidad, e.hora_aproximada
        evento.estado = "confirmado"
        fechas.add(momento.astimezone(zona).date())
        confirmados.append(evento)
    marcar_resumenes_desactualizados(db, usuario, fechas)
    db.commit()
    return [evento_publico(e, zona) for e in confirmados]


@router.post("/descartar", status_code=status.HTTP_204_NO_CONTENT)
def descartar_borradores(datos: PedidoDescarte, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Descarta borradores: no se usan en ningún análisis (HU-008, criterio 4)."""
    for evento in db.scalars(select(Evento).where(
        Evento.id_evento.in_(datos.ids), Evento.id_usuario == usuario.id_usuario, Evento.estado == "borrador"
    )):
        evento.estado = "descartado"
    db.commit()
