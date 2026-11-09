"""Consulta de los días procesados: historial (HU-014) y detalle del día (HU-012), con la asociación entre eventos y mediciones calculada al consultar (HU-010)."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analisis.asociacion import VENTANAS, asociar, duracion_de_actividad
from app.analisis.explicacion import semaforo
from app.analisis.indicadores import COBERTURA_MINIMA, gmi
from app.analisis.servicio import mediciones_del_usuario
from app.database import get_db
from app.ia import resumen as ia_resumen
from app.models import Evento, IndicadorDiario, ResumenDiario, Usuario, como_utc
from app.routers.eventos import EventoGuardado, evento_publico
from app.sesiones import usuario_actual

router = APIRouter(prefix="/dias", tags=["Días procesados"])

DIAS_MINIMOS_GMI = 14  # HU-007, criterio 4


class Indicadores(BaseModel):
    fecha: date
    rango_min: int
    rango_max: int
    tir: float
    tir_personal: float
    tbr: float
    tbr_nivel2: float
    tar: float
    tar_nivel2: float
    glucosa_promedio: float
    coeficiente_variacion: float
    cobertura: float
    parcial: bool
    mediciones_validas: int
    tiene_resumen: bool = False
    estado_resumen: str | None = None  # aprobado | plantilla | desactualizado | None (sin resumen)


class Historial(BaseModel):
    desde: date | None
    hasta: date | None
    dias: list[Indicadores]
    gmi: float | None
    gmi_detalle: str


class ValorHora(BaseModel):
    valor: int
    hora: str


class AsociacionPublica(BaseModel):
    ventana: str
    mediciones_en_ventana: int
    sin_mediciones: bool
    valor_previo: ValorHora | None
    maximo_posterior: ValorHora | None
    valor_al_finalizar: ValorHora | None
    minimo_posterior: ValorHora | None
    variacion_2h: int | None
    minimo_ventana: ValorHora | None
    maximo_ventana: ValorHora | None


class EventoAsociado(EventoGuardado):
    asociacion: AsociacionPublica


class PeriodoPublico(BaseModel):
    tipo: str
    desde: str
    hasta: str
    duracion_min: int
    valor_extremo: int
    valor_inicio: int | None
    valor_fin: int | None


class Punto(BaseModel):
    hora: str
    valor: int
    marca: str | None = None


class ResumenPublico(BaseModel):
    fecha: date
    version: int
    vigente: bool
    texto: str
    estado_verificacion: str
    motivo_generacion: str
    fecha_generacion: datetime
    modelo_utilizado: str
    observaciones: list[str]
    aviso: str = ia_resumen.AVISO


class EventoEnHorario(BaseModel):
    hora: str
    tipo: str
    descripcion: str
    cantidad: float | None
    unidad: str | None
    momento: str  # antes | durante


class Horario(BaseModel):
    desde: str
    hasta: str
    cuando: str
    duracion: str
    valor_extremo: int | None = None
    eventos: list[EventoEnHorario] = []


class EnRango(BaseModel):
    porcentaje: int
    tiempo: str
    horarios: list[Horario]


class Semaforo(BaseModel):
    rango_min: int
    rango_max: int
    horas_previas: int
    en_rango: EnRango
    alto: list[Horario]
    bajo: list[Horario]


class DetalleDia(BaseModel):
    fecha: date
    rango_min: int
    rango_max: int
    indicadores: Indicadores | None
    periodos: list[PeriodoPublico]
    puntos: list[Punto]
    eventos: list[EventoAsociado]
    dia_anterior: date | None
    dia_siguiente: date | None
    resumen: ResumenPublico | None
    # Semáforo del día: horarios en rango (verde), alta (amarillo) y baja (rojo), con los eventos de esos horarios.
    semaforo: Semaforo | None = None


def _a_indicadores(i: IndicadorDiario, resumen: ResumenDiario | None = None) -> Indicadores:
    datos = Indicadores.model_validate(i, from_attributes=True)
    if resumen is not None:
        datos.tiene_resumen = True
        datos.estado_resumen = resumen.estado_verificacion
    return datos


def _a_resumen(r: ResumenDiario) -> ResumenPublico:
    return ResumenPublico(
        fecha=r.fecha, version=r.version, vigente=r.vigente, texto=r.texto_resumen,
        estado_verificacion=r.estado_verificacion, motivo_generacion=r.motivo_generacion,
        fecha_generacion=como_utc(r.fecha_generacion), modelo_utilizado=r.modelo_utilizado,
        observaciones=[o for o in (r.observaciones or "").split("\n") if o],
    )


def _resumenes_vigentes(db: Session, usuario: Usuario, fechas) -> dict:
    filas = db.scalars(select(ResumenDiario).where(
        ResumenDiario.id_usuario == usuario.id_usuario, ResumenDiario.vigente.is_(True), ResumenDiario.fecha.in_(fechas)
    ))
    return {r.fecha: r for r in filas}


@router.get("", response_model=Historial)
def historial(
    desde: date | None = Query(None, description="Desde (AAAA-MM-DD)"),
    hasta: date | None = Query(None, description="Hasta (AAAA-MM-DD)"),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    """Días procesados del período con sus indicadores, ordenados por fecha (HU-014)."""
    consulta = select(IndicadorDiario).where(IndicadorDiario.id_usuario == usuario.id_usuario)
    if desde:
        consulta = consulta.where(IndicadorDiario.fecha >= desde)
    if hasta:
        consulta = consulta.where(IndicadorDiario.fecha <= hasta)
    dias = db.scalars(consulta.order_by(IndicadorDiario.fecha.desc())).all()

    # GMI: solo con al menos 14 días con 70 % de cobertura (criterio 4 de la HU-007).
    validos = [d for d in dias if d.cobertura >= COBERTURA_MINIMA]
    if len(validos) >= DIAS_MINIMOS_GMI:
        minutos = sum(d.cobertura for d in validos)
        promedio = sum(d.glucosa_promedio * d.cobertura for d in validos) / minutos
        valor_gmi = gmi(promedio)
        detalle = f"Calculado sobre {len(validos)} días con al menos 70 % de cobertura."
    else:
        valor_gmi = None
        detalle = (
            f"Requiere al menos {DIAS_MINIMOS_GMI} días con 70 % de cobertura "
            f"(el período tiene {len(validos)})."
        )
    resumenes = _resumenes_vigentes(db, usuario, [d.fecha for d in dias])
    return Historial(desde=desde, hasta=hasta, dias=[_a_indicadores(d, resumenes.get(d.fecha)) for d in dias],
                     gmi=valor_gmi, gmi_detalle=detalle)


def _hora(momento, zona: ZoneInfo) -> str:
    return como_utc(momento).astimezone(zona).strftime("%H:%M")


@router.get("/{fecha}", response_model=DetalleDia)
def detalle_del_dia(fecha: date, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Todo lo de un día en una sola respuesta (HU-012)."""
    config = usuario.configuracion
    zona = ZoneInfo(config.zona_horaria)
    inicio = datetime.combine(fecha, time.min, tzinfo=zona).astimezone(timezone.utc)
    fin = datetime.combine(fecha + timedelta(days=1), time.min, tzinfo=zona).astimezone(timezone.utc)

    # Incluye horas del día siguiente: una ventana puede pasar la medianoche (HU-010, criterio 5).
    margen = timedelta(hours=max(v[1] for v in VENTANAS.values()) / 60 + 12)
    mediciones = mediciones_del_usuario(db, usuario, pd.Timestamp(inicio - timedelta(hours=1)), pd.Timestamp(fin + margen))
    del_dia = mediciones[(mediciones["fecha_hora"] >= inicio) & (mediciones["fecha_hora"] < fin)]

    eventos = db.scalars(
        select(Evento).where(
            Evento.id_usuario == usuario.id_usuario, Evento.estado == "confirmado",
            Evento.fecha_hora >= inicio, Evento.fecha_hora < fin,
        ).order_by(Evento.fecha_hora)
    ).all()

    if del_dia.empty and not eventos:
        # HU-012, criterio 4: el frontend ofrece importar un archivo.
        raise HTTPException(404, "No hay mediciones importadas para ese día.")

    indicador = db.scalar(select(IndicadorDiario).where(
        IndicadorDiario.id_usuario == usuario.id_usuario, IndicadorDiario.fecha == fecha
    ))

    def vh(x):
        return ValorHora(valor=x.valor, hora=_hora(x.fecha_hora, zona)) if x else None

    eventos_asociados = []
    for e in eventos:
        a = asociar(e.tipo, como_utc(e.fecha_hora), e.hora_aproximada,
                    duracion_de_actividad(e.tipo, e.cantidad, e.unidad), mediciones)
        eventos_asociados.append(EventoAsociado(
            **evento_publico(e, zona).model_dump(),
            asociacion=AsociacionPublica(
                ventana=f"{_hora(a.ventana_desde, zona)} a {_hora(a.ventana_hasta, zona)}",
                mediciones_en_ventana=a.mediciones_en_ventana,
                sin_mediciones=a.sin_mediciones,
                valor_previo=vh(a.valor_previo),
                maximo_posterior=vh(a.maximo_posterior),
                valor_al_finalizar=vh(a.valor_al_finalizar),
                minimo_posterior=vh(a.minimo_posterior),
                variacion_2h=a.variacion_2h,
                minimo_ventana=vh(a.minimo_ventana),
                maximo_ventana=vh(a.maximo_ventana),
            ),
        ))

    anterior = db.scalar(select(IndicadorDiario.fecha).where(
        IndicadorDiario.id_usuario == usuario.id_usuario, IndicadorDiario.fecha < fecha
    ).order_by(IndicadorDiario.fecha.desc()).limit(1))
    siguiente = db.scalar(select(IndicadorDiario.fecha).where(
        IndicadorDiario.id_usuario == usuario.id_usuario, IndicadorDiario.fecha > fecha
    ).order_by(IndicadorDiario.fecha).limit(1))

    resumen = _resumenes_vigentes(db, usuario, [fecha]).get(fecha)
    semaforo_del_dia = None
    if indicador and not del_dia.empty:
        horas = del_dia["fecha_hora"].dt.tz_convert(zona).dt.strftime("%H:%M")
        datos = _datos_para_resumen(db, usuario, indicador)
        semaforo_del_dia = Semaforo(**semaforo(datos, horas.min(), horas.max()))
    return DetalleDia(
        semaforo=semaforo_del_dia,
        fecha=fecha,
        rango_min=config.rango_min,
        rango_max=config.rango_max,
        indicadores=_a_indicadores(indicador, resumen) if indicador else None,
        resumen=_a_resumen(resumen) if resumen else None,
        periodos=[
            PeriodoPublico(tipo=p.tipo, desde=_hora(p.inicio, zona), hasta=_hora(p.fin, zona),
                           duracion_min=p.duracion_min, valor_extremo=p.valor_extremo,
                           valor_inicio=p.valor_inicio, valor_fin=p.valor_fin)
            for p in (indicador.periodos if indicador else [])
        ],
        puntos=[Punto(hora=f.tz_convert(zona).strftime("%H:%M"), valor=int(v))
                for f, v in zip(del_dia["fecha_hora"], del_dia["valor"])],
        eventos=eventos_asociados,
        dia_anterior=anterior,
        dia_siguiente=siguiente,
    )


# Resumen diario (HU-013)

def _datos_para_resumen(db: Session, usuario: Usuario, indicador: IndicadorDiario) -> ia_resumen.DatosDia:
    """Solo valores ya calculados por el sistema y eventos confirmados (nada de la serie completa)."""
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    inicio = datetime.combine(indicador.fecha, time.min, tzinfo=zona).astimezone(timezone.utc)
    fin = datetime.combine(indicador.fecha + timedelta(days=1), time.min, tzinfo=zona).astimezone(timezone.utc)
    eventos = db.scalars(select(Evento).where(
        Evento.id_usuario == usuario.id_usuario, Evento.estado == "confirmado",
        Evento.fecha_hora >= inicio, Evento.fecha_hora < fin,
    ).order_by(Evento.fecha_hora)).all()
    return ia_resumen.DatosDia(
        fecha=indicador.fecha, rango_min=indicador.rango_min, rango_max=indicador.rango_max,
        tir=indicador.tir, tir_personal=indicador.tir_personal, tbr=indicador.tbr, tbr_nivel2=indicador.tbr_nivel2,
        tar=indicador.tar, tar_nivel2=indicador.tar_nivel2, glucosa_promedio=indicador.glucosa_promedio,
        coeficiente_variacion=indicador.coeficiente_variacion, cobertura=indicador.cobertura,
        parcial=indicador.parcial, mediciones=indicador.mediciones_validas,
        periodos=[ia_resumen.PeriodoDatos(p.tipo, _hora(p.inicio, zona), _hora(p.fin, zona), p.duracion_min,
                                          p.valor_extremo, p.valor_inicio, p.valor_fin) for p in indicador.periodos],
        eventos=[ia_resumen.EventoDatos(_hora(e.fecha_hora, zona), e.tipo, e.descripcion, e.cantidad, e.unidad)
                 for e in eventos],
    )


@router.post("/{fecha}/resumen", response_model=ResumenPublico)
def generar_resumen(fecha: date, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Genera una nueva versión del resumen del día (HU-013): el modelo redacta a partir de los datos calculados, el sistema lo verifica y, si no se aprueba, usa la plantilla."""
    indicador = db.scalar(select(IndicadorDiario).where(
        IndicadorDiario.id_usuario == usuario.id_usuario, IndicadorDiario.fecha == fecha
    ))
    if not indicador:
        raise HTTPException(404, "No hay indicadores calculados para ese día: importá sus mediciones primero.")

    anterior = _resumenes_vigentes(db, usuario, [fecha]).get(fecha)
    resultado = ia_resumen.generar(_datos_para_resumen(db, usuario, indicador))

    ultima_version = db.scalar(select(func.max(ResumenDiario.version)).where(
        ResumenDiario.id_usuario == usuario.id_usuario, ResumenDiario.fecha == fecha
    )) or 0
    if anterior:
        anterior.vigente = False
    nuevo = ResumenDiario(
        id_usuario=usuario.id_usuario, id_indicador=indicador.id_indicador, fecha=fecha,
        version=ultima_version + 1, vigente=True, texto_resumen=resultado.texto,
        estado_verificacion=resultado.estado,
        motivo_generacion=("actualización de datos" if anterior and anterior.estado_verificacion == "desactualizado"
                           else "regeneración solicitada" if anterior else "solicitud"),
        modelo_utilizado=resultado.modelo,
        observaciones="\n".join(resultado.observaciones) or None,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _a_resumen(nuevo)


@router.get("/{fecha}/resumenes", response_model=list[ResumenPublico])
def versiones_del_resumen(fecha: date, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Todas las versiones del resumen de un día, la más reciente primero."""
    filas = db.scalars(select(ResumenDiario).where(
        ResumenDiario.id_usuario == usuario.id_usuario, ResumenDiario.fecha == fecha
    ).order_by(ResumenDiario.version.desc())).all()
    return [_a_resumen(r) for r in filas]
