"""Cálculo de los indicadores glucémicos diarios (HU-007) y detección de los períodos relevantes (HU-011), con Pandas."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

# Umbrales del Consenso Internacional sobre Tiempo en Rango (Battelino et al., 2019).
UMBRAL_BAJO_N2 = 54
UMBRAL_BAJO = 70
UMBRAL_ALTO = 180
UMBRAL_ALTO_N2 = 250
COBERTURA_MINIMA = 70.0  # % (criterio 3)
MINUTOS_DIA = 1440

# Períodos relevantes (HU-011)
DURACION_MINIMA = 15        # minutos consecutivos fuera de rango
CAMBIO_MINIMO = 60          # mg/dL  } variación rápida: un cambio de al menos 60 mg/dL
VENTANA_CAMBIO = 60         # min    } en 60 minutos o menos


@dataclass
class Periodo:
    tipo: str               # bajo | sobre | bajo_nivel2 | sobre_nivel2 | subida | bajada
    inicio: datetime        # UTC
    fin: datetime           # UTC
    duracion_min: int
    valor_extremo: int      # mínimo (bajos, bajada) o máximo (altos, subida)
    valor_inicio: int | None = None  # para los períodos de variación
    valor_fin: int | None = None


@dataclass
class IndicadoresDia:
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
    frecuencia_min: int
    periodos: list[Periodo] = field(default_factory=list)


def limites_del_dia(fecha: date, zona: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Inicio y fin del día local, en UTC."""
    tz = ZoneInfo(zona)
    inicio = datetime.combine(fecha, time.min, tzinfo=tz)
    fin = datetime.combine(fecha + timedelta(days=1), time.min, tzinfo=tz)
    return pd.Timestamp(inicio).tz_convert("UTC"), pd.Timestamp(fin).tz_convert("UTC")


def frecuencia_del_sensor(momentos: pd.Series) -> int:
    """Intervalo habitual entre mediciones, en minutos (5 o 15 según el sensor)."""
    diferencias = momentos.sort_values().diff().dropna().dt.total_seconds() / 60
    diferencias = diferencias[diferencias > 0]
    if diferencias.empty:
        return 5
    return max(1, int(round(diferencias.median())))


def _ponderar(serie: pd.DataFrame, inicio: pd.Timestamp, fin: pd.Timestamp, frecuencia: int) -> pd.DataFrame:
    """Agrega a cada medición el tramo de tiempo que representa (desde, hasta) recortado al día, y su peso en minutos."""
    s = serie.sort_values("fecha_hora").drop_duplicates("fecha_hora").reset_index(drop=True)
    siguiente = s["fecha_hora"].shift(-1)
    intervalo = (siguiente - s["fecha_hora"]).dt.total_seconds() / 60
    maximo = 2 * frecuencia
    # Intervalo normal: vale hasta la siguiente. Hueco (o última medición): vale una frecuencia.
    duracion = intervalo.where(intervalo <= maximo, frecuencia).fillna(frecuencia)
    desde = s["fecha_hora"]
    hasta = desde + pd.to_timedelta(duracion, unit="min")
    s["desde"] = desde.clip(lower=inicio)
    s["hasta"] = hasta.clip(upper=fin)
    s["peso"] = ((s["hasta"] - s["desde"]).dt.total_seconds() / 60).clip(lower=0)
    s["hueco_despues"] = intervalo > maximo
    return s[s["peso"] > 0].reset_index(drop=True)


def _porcentaje(pesos: pd.Series, condicion: pd.Series, total: float) -> float:
    return round(float(pesos[condicion].sum()) / total * 100, 1) if total else 0.0


def calcular_dia(
    mediciones: pd.DataFrame,
    fecha: date,
    zona: str,
    rango_min: int,
    rango_max: int,
    frecuencia: int | None = None,
) -> IndicadoresDia | None:
    """mediciones: columnas fecha_hora (UTC, con zona) y valor (mg/dL)."""
    inicio, fin = limites_del_dia(fecha, zona)
    if mediciones.empty:
        return None
    if frecuencia is None:
        frecuencia = frecuencia_del_sensor(mediciones["fecha_hora"])

    margen = pd.Timedelta(minutes=2 * frecuencia)
    cercanas = mediciones[(mediciones["fecha_hora"] >= inicio - margen) & (mediciones["fecha_hora"] < fin)]
    s = _ponderar(cercanas, inicio, fin, frecuencia)
    del_dia = s[(s["fecha_hora"] >= inicio) & (s["fecha_hora"] < fin)]
    if del_dia.empty:
        return None

    v, w = s["valor"], s["peso"]
    total = float(w.sum())
    promedio = float((v * w).sum() / total)
    desvio = float((((v - promedio) ** 2) * w).sum() / total) ** 0.5
    cobertura = round(total / MINUTOS_DIA * 100, 1)

    return IndicadoresDia(
        fecha=fecha,
        rango_min=rango_min,
        rango_max=rango_max,
        tir=_porcentaje(w, (v >= UMBRAL_BAJO) & (v <= UMBRAL_ALTO), total),
        tir_personal=_porcentaje(w, (v >= rango_min) & (v <= rango_max), total),
        tbr=_porcentaje(w, v < UMBRAL_BAJO, total),
        tbr_nivel2=_porcentaje(w, v < UMBRAL_BAJO_N2, total),
        tar=_porcentaje(w, v > UMBRAL_ALTO, total),
        tar_nivel2=_porcentaje(w, v > UMBRAL_ALTO_N2, total),
        glucosa_promedio=round(promedio, 1),
        coeficiente_variacion=round(desvio / promedio * 100, 1) if promedio else 0.0,
        cobertura=min(cobertura, 100.0),
        parcial=cobertura < COBERTURA_MINIMA,
        mediciones_validas=len(del_dia),
        frecuencia_min=frecuencia,
        periodos=detectar_periodos(s, rango_min, rango_max),
    )


# Períodos relevantes (HU-011)

def _tramos(s: pd.DataFrame, condicion: pd.Series) -> list[pd.DataFrame]:
    """Agrupa mediciones consecutivas que cumplen la condición (un hueco corta el tramo)."""
    tramos, actual = [], []
    for i in range(len(s)):
        if condicion.iloc[i]:
            actual.append(i)
            if s["hueco_despues"].iloc[i]:
                tramos.append(actual)
                actual = []
        elif actual:
            tramos.append(actual)
            actual = []
    if actual:
        tramos.append(actual)
    return [s.iloc[t] for t in tramos]


def _periodos_fuera_de_rango(s: pd.DataFrame, condicion: pd.Series, tipo: str, usar_minimo: bool) -> list[Periodo]:
    periodos = []
    for tramo in _tramos(s, condicion):
        inicio, fin = tramo["desde"].iloc[0], tramo["hasta"].iloc[-1]
        duracion = (fin - inicio).total_seconds() / 60
        if duracion >= DURACION_MINIMA:
            extremo = tramo["valor"].min() if usar_minimo else tramo["valor"].max()
            periodos.append(Periodo(tipo, inicio.to_pydatetime(), fin.to_pydatetime(), int(round(duracion)), int(extremo)))
    return periodos


def _segmentos_sin_huecos(s: pd.DataFrame) -> list[pd.DataFrame]:
    """Divide las mediciones en tramos continuos: un hueco (intervalo > 2 frecuencias) corta el tramo."""
    cortes = s["hueco_despues"].shift(1, fill_value=False).cumsum()
    return [g.reset_index(drop=True) for _, g in s.groupby(cortes)]


def _periodos_de_variacion(s: pd.DataFrame) -> list[Periodo]:
    """Regla única de variación rápida (HU-011, criterio 3)"""
    periodos: list[Periodo] = []
    limite = pd.Timedelta(minutes=VENTANA_CAMBIO)
    for tramo in _segmentos_sin_huecos(s):
        if len(tramo) < 2:
            continue
        momentos = tramo["fecha_hora"].tolist()
        valores = tramo["valor"].astype(int).tolist()
        for sentido in (1, -1):
            # 1. Ventanas que cumplen la regla, como pares de índices (inicio, fin).
            ventanas = []
            for i in range(len(tramo)):
                for k in range(i + 1, len(tramo)):
                    if momentos[k] - momentos[i] > limite:
                        break
                    if (valores[k] - valores[i]) * sentido >= CAMBIO_MINIMO:
                        ventanas.append((i, k))
            # 2. Unión de ventanas superpuestas.
            grupos: list[list[int]] = []
            for i, k in sorted(ventanas):
                if grupos and i <= grupos[-1][1]:
                    grupos[-1][1] = max(grupos[-1][1], k)
                else:
                    grupos.append([i, k])
            # 3. Inicio en el extremo de partida y fin en el extremo de llegada.
            for a, b in grupos:
                tramo_valores = valores[a:b + 1]
                if sentido > 0:
                    fin = a + max(range(len(tramo_valores)), key=lambda x: (tramo_valores[x], -x))
                    inicio = a + min(range(fin - a + 1), key=lambda x: (tramo_valores[x], -x))
                else:
                    fin = a + min(range(len(tramo_valores)), key=lambda x: (tramo_valores[x], x))
                    inicio = a + max(range(fin - a + 1), key=lambda x: (tramo_valores[x], x))
                duracion = (momentos[fin] - momentos[inicio]).total_seconds() / 60
                periodos.append(Periodo(
                    "subida" if sentido > 0 else "bajada",
                    momentos[inicio].to_pydatetime(), momentos[fin].to_pydatetime(), int(round(duracion)),
                    valores[fin], valor_inicio=valores[inicio], valor_fin=valores[fin],
                ))
    return periodos


def detectar_periodos(s: pd.DataFrame, rango_min: int, rango_max: int) -> list[Periodo]:
    """s: mediciones ponderadas del día (salida de _ponderar)."""
    v = s["valor"]
    periodos = (
        _periodos_fuera_de_rango(s, v < rango_min, "bajo", True)
        + _periodos_fuera_de_rango(s, v > rango_max, "sobre", False)
        + _periodos_fuera_de_rango(s, v < UMBRAL_BAJO_N2, "bajo_nivel2", True)
        + _periodos_fuera_de_rango(s, v > UMBRAL_ALTO_N2, "sobre_nivel2", False)
        + _periodos_de_variacion(s)
    )
    return sorted(periodos, key=lambda p: p.inicio)


def gmi(glucosa_promedio: float) -> float:
    """Indicador de Gestión de Glucosa (Bergenstal et al., 2018), en %."""
    return round(3.31 + 0.02392 * glucosa_promedio, 1)
