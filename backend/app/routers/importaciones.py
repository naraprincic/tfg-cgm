"""Importación de archivos de mediciones del CGM (HU-005) y su validación (HU-006)."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analisis.servicio import recalcular
from app.database import get_db
from app.importacion.adaptadores import ArchivoRechazado, leer_archivo
from app.importacion.validacion import FormatoFechaRequerido, _clave, validar
from app.models import Importacion, Medicion, Usuario, como_utc
from app.sesiones import usuario_actual

router = APIRouter(prefix="/importaciones", tags=["Importación de mediciones"])

TAMANO_MAXIMO = 10 * 1024 * 1024  # 10 MB


class Detalle(BaseModel):
    fila: int
    motivo: str


class OpcionFormato(BaseModel):
    id: str
    nombre: str
    ejemplo: str
    filas_legibles: int
    total: int


class ResumenValidacion(BaseModel):
    """Lo que se le muestra a la persona antes de confirmar (y después de importar)."""

    nombre_archivo: str
    formato: str | None
    aceptado: bool
    motivo_rechazo: str | None
    filas_glucosa: int = 0
    filas_invalidas: int = 0
    filas_duplicadas: int = 0
    filas_en_conflicto: int = 0
    mediciones_nuevas: int = 0
    dias: int = 0
    desde: str | None = None
    hasta: str | None = None
    detalle_invalidas: list[Detalle] = []
    detalle_conflictos: list[Detalle] = []
    id_importacion: int | None = None
    formato_fecha: str | None = None
    zona_horaria: str | None = None
    # Formato regional de fecha sin confirmar (HU-006): la persona elige una opción y se valida de nuevo.
    requiere_formato_fecha: bool = False
    opciones_formato_fecha: list[OpcionFormato] = []


class ImportacionListada(BaseModel):
    id_importacion: int
    nombre_archivo: str
    formato: str | None
    fecha_importacion: datetime
    estado: str
    motivo_rechazo: str | None
    mediciones_incorporadas: int
    filas_invalidas: int
    filas_duplicadas: int
    filas_en_conflicto: int
    dias: int
    formato_fecha: str | None
    zona_horaria: str | None
    periodo_desde: datetime | None
    periodo_hasta: datetime | None


def _buscador(db: Session, usuario: Usuario):
    """Devuelve la función que busca las mediciones ya guardadas de ESTE usuario."""

    def buscar(origenes: list[str], desde: datetime, hasta: datetime) -> dict:
        filas = db.execute(
            select(Medicion.origen, Medicion.fecha_hora, Medicion.valor).where(
                Medicion.id_usuario == usuario.id_usuario,  # siempre filtrado por el titular
                Medicion.origen.in_(origenes),
                Medicion.fecha_hora >= desde,
                Medicion.fecha_hora <= hasta,
            )
        )
        return {_clave(o, como_utc(f)): v for o, f, v in filas}

    return buscar


async def _procesar(archivo: UploadFile, db: Session, usuario: Usuario, formato_fecha: str | None):
    """Lee y valida el archivo. Devuelve (resumen, resultado o None si se rechazó)."""
    nombre = archivo.filename or "archivo"
    zona = usuario.configuracion.zona_horaria
    contenido = await archivo.read(TAMANO_MAXIMO + 1)
    try:
        if len(contenido) > TAMANO_MAXIMO:
            raise ArchivoRechazado("El archivo supera el tamaño máximo de 10 MB.")
        leidas = leer_archivo(nombre, contenido)
        resultado = validar(leidas, zona, _buscador(db, usuario), formato_fecha)
    except ArchivoRechazado as rechazo:
        return ResumenValidacion(nombre_archivo=nombre, formato=None, aceptado=False,
                                 motivo_rechazo=str(rechazo), zona_horaria=zona), None
    except FormatoFechaRequerido as pedido:
        return ResumenValidacion(
            nombre_archivo=nombre, formato=leidas.formato, aceptado=False, zona_horaria=zona,
            motivo_rechazo=("Las fechas del archivo pueden leerse como día-mes o como mes-día. "
                            "Confirmá el formato para continuar."),
            requiere_formato_fecha=True, opciones_formato_fecha=pedido.opciones,
        ), None

    datos = {k: v for k, v in vars(resultado).items() if k != "nuevas"}
    return ResumenValidacion(nombre_archivo=nombre, zona_horaria=zona, **datos), resultado


def _registrar_rechazo(db: Session, usuario: Usuario, resumen: ResumenValidacion) -> None:
    """Las importaciones rechazadas también figuran en el listado, con su motivo."""
    db.add(Importacion(
        id_usuario=usuario.id_usuario,
        nombre_archivo=resumen.nombre_archivo[:255],
        formato=resumen.formato,
        estado="rechazada",
        motivo_rechazo=resumen.motivo_rechazo,
        filas_glucosa=resumen.filas_glucosa,
        filas_invalidas=resumen.filas_invalidas,
        filas_duplicadas=resumen.filas_duplicadas,
        filas_en_conflicto=resumen.filas_en_conflicto,
        formato_fecha=resumen.formato_fecha,
        zona_horaria=resumen.zona_horaria,
    ))
    db.commit()


@router.post("/validar", response_model=ResumenValidacion)
async def validar_archivo(
    archivo: UploadFile = File(...),
    formato_fecha: str | None = Form(None, description="Variante regional confirmada: dia-mes o mes-dia"),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    """Valida el archivo sin guardar mediciones (HU-006). Si se rechaza, se registra el motivo."""
    resumen, _ = await _procesar(archivo, db, usuario, formato_fecha)
    if not resumen.aceptado and not resumen.requiere_formato_fecha:
        _registrar_rechazo(db, usuario, resumen)
    return resumen


@router.post("", response_model=ResumenValidacion, status_code=status.HTTP_201_CREATED)
async def importar_archivo(
    archivo: UploadFile = File(...),
    formato_fecha: str | None = Form(None, description="Variante regional confirmada: dia-mes o mes-dia"),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    """Importa el archivo ya validado (HU-005)."""
    resumen, resultado = await _procesar(archivo, db, usuario, formato_fecha)
    if not resumen.aceptado:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, resumen.motivo_rechazo)

    try:
        importacion = Importacion(
            id_usuario=usuario.id_usuario,
            nombre_archivo=resumen.nombre_archivo[:255],
            formato=resumen.formato,
            estado="completada",
            filas_glucosa=resumen.filas_glucosa,
            mediciones_incorporadas=resumen.mediciones_nuevas,
            filas_invalidas=resumen.filas_invalidas,
            filas_duplicadas=resumen.filas_duplicadas,
            filas_en_conflicto=resumen.filas_en_conflicto,
            dias=resumen.dias,
            formato_fecha=resumen.formato_fecha,
            zona_horaria=resumen.zona_horaria,
            periodo_desde=resultado.nuevas["fecha_hora"].min().to_pydatetime() if len(resultado.nuevas) else None,
            periodo_hasta=resultado.nuevas["fecha_hora"].max().to_pydatetime() if len(resultado.nuevas) else None,
        )
        db.add(importacion)
        db.flush()  # obtiene el id de la importación sin confirmar todavía
        db.add_all(
            Medicion(
                id_importacion=importacion.id_importacion,
                id_usuario=usuario.id_usuario,
                fecha_hora=fila.fecha_hora.to_pydatetime(),
                valor=int(fila.valor),
                origen=fila.origen,
                marca=fila.marca if isinstance(fila.marca, str) else None,
            )
            for fila in resultado.nuevas.itertuples(index=False)
        )
        db.flush()  # las mediciones nuevas tienen que estar visibles para el recálculo
        # HU-007, criterio 5: se recalculan los indicadores de los días afectados.
        zona = usuario.configuracion.zona_horaria
        recalcular(db, usuario, set(resultado.nuevas["fecha_hora"].dt.tz_convert(zona).dt.date.unique()))
        db.commit()  # todo o nada
    except Exception:
        db.rollback()  # criterio 3: se conserva el estado anterior
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Ocurrió un error al guardar las mediciones. No se incorporó ninguna; probá de nuevo.",
        )

    resumen.id_importacion = importacion.id_importacion
    return resumen


@router.get("", response_model=list[ImportacionListada])
def listar_importaciones(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Importaciones anteriores del usuario, la más reciente primero."""
    return db.scalars(
        select(Importacion)
        .where(Importacion.id_usuario == usuario.id_usuario)
        .order_by(Importacion.fecha_importacion.desc(), Importacion.id_importacion.desc())
    ).all()
