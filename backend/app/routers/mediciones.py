"""Consulta de las mediciones almacenadas, para comprobar la importación y graficar un día."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Medicion, Usuario, como_utc
from app.sesiones import usuario_actual

router = APIRouter(prefix="/mediciones", tags=["Mediciones"])


class DiaConMediciones(BaseModel):
    fecha: date
    cantidad: int
    minimo: int
    maximo: int
    promedio: int


class Punto(BaseModel):
    hora: str          # HH:MM en la zona horaria del usuario
    fecha_hora: datetime
    valor: int
    marca: str | None


@router.get("/dias", response_model=list[DiaConMediciones])
def dias_con_mediciones(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Lista los días que tienen mediciones, del más reciente al más antiguo."""
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    filas = db.execute(
        select(Medicion.fecha_hora, Medicion.valor).where(Medicion.id_usuario == usuario.id_usuario)
    )
    por_dia: dict[date, list[int]] = {}
    for fecha_hora, valor in filas:
        por_dia.setdefault(como_utc(fecha_hora).astimezone(zona).date(), []).append(valor)
    return [
        DiaConMediciones(fecha=d, cantidad=len(v), minimo=min(v), maximo=max(v), promedio=round(sum(v) / len(v)))
        for d, v in sorted(por_dia.items(), reverse=True)
    ]


@router.get("", response_model=list[Punto])
def mediciones_del_dia(
    fecha: date = Query(..., description="Día a consultar (AAAA-MM-DD)"),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    """Mediciones de un día, en la zona horaria configurada por el usuario."""
    zona = ZoneInfo(usuario.configuracion.zona_horaria)
    # Límites del día local, expresados en UTC (así se guardan las mediciones).
    inicio = datetime.combine(fecha, time.min, tzinfo=zona).astimezone(timezone.utc)
    fin = datetime.combine(fecha + timedelta(days=1), time.min, tzinfo=zona).astimezone(timezone.utc)
    filas = db.scalars(
        select(Medicion)
        .where(
            Medicion.id_usuario == usuario.id_usuario,
            Medicion.fecha_hora >= inicio,
            Medicion.fecha_hora < fin,
        )
        .order_by(Medicion.fecha_hora)
    ).all()
    if not filas:
        raise HTTPException(404, "No hay mediciones para ese día.")
    return [
        Punto(
            hora=como_utc(m.fecha_hora).astimezone(zona).strftime("%H:%M"),
            fecha_hora=como_utc(m.fecha_hora),
            valor=m.valor,
            marca=m.marca,
        )
        for m in filas
    ]
