"""Recalcula y guarda los indicadores diarios y sus períodos relevantes."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.analisis.indicadores import calcular_dia, frecuencia_del_sensor, limites_del_dia
from app.models import IndicadorDiario, Medicion, PeriodoRelevante, ResumenDiario, Usuario, como_utc

CAMPOS = ["rango_min", "rango_max", "tir", "tir_personal", "tbr", "tbr_nivel2", "tar", "tar_nivel2",
          "glucosa_promedio", "coeficiente_variacion", "cobertura", "parcial", "mediciones_validas"]


def mediciones_del_usuario(
    db: Session, usuario: Usuario, desde=None, hasta=None
) -> pd.DataFrame:
    """Mediciones del usuario como tabla de Pandas (fecha_hora en UTC, valor), ordenadas."""
    consulta = select(Medicion.fecha_hora, Medicion.valor).where(Medicion.id_usuario == usuario.id_usuario)
    if desde is not None:
        consulta = consulta.where(Medicion.fecha_hora >= desde.to_pydatetime())
    if hasta is not None:
        consulta = consulta.where(Medicion.fecha_hora < hasta.to_pydatetime())
    filas = db.execute(consulta.order_by(Medicion.fecha_hora)).all()
    tabla = pd.DataFrame(filas, columns=["fecha_hora", "valor"])
    if tabla.empty:
        return pd.DataFrame({"fecha_hora": pd.Series(dtype="datetime64[ns, UTC]"), "valor": pd.Series(dtype=int)})
    tabla["fecha_hora"] = pd.to_datetime([como_utc(f) for f in tabla["fecha_hora"]], utc=True)
    return tabla


def fechas_locales(mediciones: pd.DataFrame, zona: str) -> set[date]:
    if mediciones.empty:
        return set()
    return set(mediciones["fecha_hora"].dt.tz_convert(ZoneInfo(zona)).dt.date.unique())


def marcar_resumenes_desactualizados(db: Session, usuario: Usuario, fechas: set[date]) -> None:
    """HU-013, criterio 4: el resumen vigente de esas fechas pasa a desactualizado."""
    if not fechas:
        return
    db.execute(
        update(ResumenDiario)
        .where(ResumenDiario.id_usuario == usuario.id_usuario, ResumenDiario.fecha.in_(fechas),
               ResumenDiario.vigente.is_(True))
        .values(estado_verificacion="desactualizado")
    )


def recalcular(db: Session, usuario: Usuario, fechas: set[date] | None = None) -> int:
    """Recalcula los días indicados (o todos, si fechas es None)."""
    config = usuario.configuracion
    zona = config.zona_horaria
    todas = mediciones_del_usuario(db, usuario)
    dias_con_datos = fechas_locales(todas, zona)

    consulta = select(IndicadorDiario).where(IndicadorDiario.id_usuario == usuario.id_usuario)
    if fechas is None:
        objetivo = dias_con_datos
    else:
        # Un día vecino puede cambiar por la ponderación en la medianoche.
        objetivo = {f + timedelta(days=d) for f in fechas for d in (-1, 0, 1)}
        consulta = consulta.where(IndicadorDiario.fecha.in_(objetivo))
    existentes = {i.fecha: i for i in db.scalars(consulta)}
    objetivo = objetivo | set(existentes)

    cambiaron: set[date] = set()
    calculados = 0
    for fecha in sorted(objetivo):
        anterior = existentes.get(fecha)
        resultado = None
        if fecha in dias_con_datos:
            inicio, fin = limites_del_dia(fecha, zona)
            cercanas = todas[(todas["fecha_hora"] >= inicio - pd.Timedelta(hours=1)) & (todas["fecha_hora"] < fin)]
            del_dia = cercanas[cercanas["fecha_hora"] >= inicio]
            resultado = calcular_dia(
                cercanas, fecha, zona, config.rango_min, config.rango_max,
                frecuencia=frecuencia_del_sensor(del_dia["fecha_hora"]),
            )
        if resultado is None:
            if anterior is not None:
                db.delete(anterior)  # el día ya no tiene mediciones
            continue

        valores = {c: getattr(resultado, c) for c in CAMPOS}
        if anterior is None:
            indicador = IndicadorDiario(id_usuario=usuario.id_usuario, fecha=fecha, **valores)
            db.add(indicador)
        else:
            indicador = anterior
            if any(getattr(indicador, c) != v for c, v in valores.items()):
                cambiaron.add(fecha)
            for c, v in valores.items():
                setattr(indicador, c, v)
            indicador.periodos.clear()
        db.flush()
        indicador.periodos.extend(
            PeriodoRelevante(
                id_indicador=indicador.id_indicador,
                id_usuario=usuario.id_usuario,
                tipo=p.tipo,
                inicio=p.inicio,
                fin=p.fin,
                duracion_min=p.duracion_min,
                valor_extremo=p.valor_extremo,
                valor_inicio=p.valor_inicio,
                valor_fin=p.valor_fin,
            )
            for p in resultado.periodos
        )
        calculados += 1

    marcar_resumenes_desactualizados(db, usuario, cambiaron)
    db.flush()
    return calculados
