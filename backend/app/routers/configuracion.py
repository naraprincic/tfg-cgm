"""Configuración del rango objetivo y las preferencias (HU-004)."""

from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from app.analisis.servicio import recalcular
from app.database import get_db
from app.models import Usuario
from app.sesiones import usuario_actual

router = APIRouter(prefix="/configuracion", tags=["Configuración"])

LIMITE_INFERIOR = 40   # intervalo admitido (HU-004, criterio 2)
LIMITE_SUPERIOR = 300


class Configuracion(BaseModel):
    rango_min: int
    rango_max: int
    zona_horaria: str = "America/Argentina/Buenos_Aires"

    @field_validator("rango_min", "rango_max")
    @classmethod
    def dentro_del_intervalo(cls, valor: int) -> int:
        if not LIMITE_INFERIOR <= valor <= LIMITE_SUPERIOR:
            raise ValueError(f"Debe estar entre {LIMITE_INFERIOR} y {LIMITE_SUPERIOR} mg/dL.")
        return valor

    @field_validator("zona_horaria")
    @classmethod
    def zona_valida(cls, valor: str) -> str:
        if valor not in available_timezones():
            raise ValueError("La zona horaria no es válida.")
        ZoneInfo(valor)
        return valor

    @model_validator(mode="after")
    def minimo_menor_que_maximo(self):
        # Criterio 1: límite inferior mayor o igual al superior.
        if self.rango_min >= self.rango_max:
            raise ValueError("El límite inferior debe ser menor que el superior.")
        return self


class ConfiguracionGuardada(Configuracion):
    mensaje: str
    dias_recalculados: int


@router.get("", response_model=Configuracion)
def obtener(usuario: Usuario = Depends(usuario_actual)):
    c = usuario.configuracion
    return Configuracion(rango_min=c.rango_min, rango_max=c.rango_max, zona_horaria=c.zona_horaria)


@router.put("", response_model=ConfiguracionGuardada)
def guardar(datos: Configuracion, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Guarda el rango personal y recalcula los indicadores y períodos de todos los días (criterio 4)."""
    c = usuario.configuracion
    c.rango_min, c.rango_max, c.zona_horaria = datos.rango_min, datos.rango_max, datos.zona_horaria
    db.flush()
    dias = recalcular(db, usuario)
    db.commit()
    return ConfiguracionGuardada(
        **datos.model_dump(),
        dias_recalculados=dias,
        mensaje=(
            f"Configuración guardada. Se recalcularon los indicadores de {dias} "
            f"{'día' if dias == 1 else 'días'}." if dias else "Configuración guardada."
        ),
    )
