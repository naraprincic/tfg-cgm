"""Pruebas del cálculo de indicadores (HU-007) y de los períodos relevantes (HU-011)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.analisis.indicadores import calcular_dia, gmi

ZONA = "America/Argentina/Buenos_Aires"
DIA = date(2026, 10, 15)


def serie(valores: list[int], desde="10:00", cada=5) -> pd.DataFrame:
    """Mediciones a partir de una hora local, una cada `cada` minutos."""
    h, m = map(int, desde.split(":"))
    inicio = datetime(2026, 10, 15, h, m, tzinfo=ZoneInfo(ZONA))
    momentos = [inicio + timedelta(minutes=cada * i) for i in range(len(valores))]
    return pd.DataFrame({"fecha_hora": pd.to_datetime(momentos, utc=True), "valor": valores})


def calcular(df, rango=(70, 180), frecuencia=5):
    return calcular_dia(df, DIA, ZONA, rango[0], rango[1], frecuencia=frecuencia)


# --- Criterio 2: indicadores ------------------------------------------------

def test_indicadores_calculados_a_mano():
    # 4 mediciones de 5 minutos cada una: 60, 100, 200, 260 (20 minutos en total).
    r = calcular(serie([60, 100, 200, 260]))
    assert r.tir == 25.0          # solo 100 está entre 70 y 180
    assert r.tbr == 25.0          # 60
    assert r.tbr_nivel2 == 0.0    # ninguna por debajo de 54
    assert r.tar == 50.0          # 200 y 260
    assert r.tar_nivel2 == 25.0   # 260
    assert r.glucosa_promedio == 155.0  # (60 + 100 + 200 + 260) / 4
    # Desvío = raíz((95² + 55² + 45² + 105²) / 4) = 79,21  ->  CV = 79,21 / 155 × 100 = 51,1 %
    assert r.coeficiente_variacion == 51.1
    assert r.mediciones_validas == 4


def test_tiempo_en_rango_personal_usa_el_rango_configurado():
    r = calcular(serie([75, 100, 150]), rango=(80, 140))
    assert r.tir_personal == pytest.approx(33.3)  # solo 100 está entre 80 y 140
    assert r.tir == 100.0                         # el consenso (70–180) no cambia


def test_ponderacion_por_tiempo():
    # 100 dura 10 minutos y 200 dura 5 (cuando el sensor mide cada 5): el promedio pondera.
    df = pd.concat([serie([100], "10:00"), serie([200], "10:10")])
    r = calcular(df)
    assert r.glucosa_promedio == pytest.approx((100 * 10 + 200 * 5) / 15, abs=0.1)


# --- Criterio 1: huecos ------------------------------------------------------

def test_los_huecos_no_se_interpolan_y_bajan_la_cobertura():
    # Dos mediciones separadas por 30 minutos con un sensor de 5: es un hueco.
    df = pd.concat([serie([100], "10:00"), serie([300], "10:30")])
    r = calcular(df)
    assert r.cobertura == pytest.approx(10 / 1440 * 100, abs=0.1)  # 5 + 5 minutos con datos
    assert r.glucosa_promedio == 200.0  # cada una vale 5 minutos, no 30


def test_dia_completo():
    r = calcular(serie([120] * 288, "00:00"))
    assert r.cobertura == 100.0 and not r.parcial
    assert r.tir == 100.0 and r.coeficiente_variacion == 0.0


# --- Criterio 3: cobertura insuficiente --------------------------------------

def test_cobertura_menor_al_70_por_ciento_es_parcial():
    r = calcular(serie([120] * 200, "00:00"))  # 200 × 5 = 1000 minutos = 69,4 %
    assert r.parcial and r.cobertura == pytest.approx(69.4)


# --- Criterio 4: GMI ---------------------------------------------------------

def test_gmi():
    assert gmi(154) == 7.0  # 3,31 + 0,02392 × 154 = 6,99


# --- HU-011: períodos relevantes ---------------------------------------------

def tipos(r):
    return [p.tipo for p in r.periodos]


def test_periodo_bajo_rango_de_al_menos_15_minutos():
    # Base de 90 para que la caída (30 mg/dL) no cuente además como variación rápida.
    r = calcular(serie([90] * 6 + [65, 62, 60, 66] + [90] * 6))
    assert tipos(r) == ["bajo"]
    p = r.periodos[0]
    assert p.duracion_min == 20 and p.valor_extremo == 60


def test_menos_de_15_minutos_no_es_periodo():
    r = calcular(serie([90] * 6 + [65, 62] + [90] * 6))  # 10 minutos
    assert r.periodos == []


def test_periodo_de_nivel_2():
    r = calcular(serie([80] * 6 + [50, 48, 52] + [80] * 6))
    assert sorted(tipos(r)) == ["bajo", "bajo_nivel2"]


def test_periodo_sobre_rango_con_rango_personal():
    r = calcular(serie([120] * 6 + [150, 155, 160] + [120] * 6), rango=(70, 140))
    assert tipos(r) == ["sobre"] and r.periodos[0].valor_extremo == 160


def test_caida_brusca_cuenta_como_variacion():
    # De 120 a 60 en 5 minutos: además del período bajo, es una variación rápida (bajada).
    r = calcular(serie([120] * 6 + [65, 62, 60, 66] + [120] * 6))
    assert "bajada" in tipos(r) and "bajo" in tipos(r)


def test_periodo_de_variacion_rapida():
    # Sube de 100 a 200 en 30 minutos (más de 3 mg/dL por minuto) y luego se estabiliza.
    subida = [100, 115, 132, 150, 168, 185, 200]
    r = calcular(serie([100] * 6 + subida + [200] * 8))
    variacion = [p for p in r.periodos if p.tipo == "subida"]
    assert len(variacion) == 1
    assert variacion[0].valor_fin - variacion[0].valor_inicio >= 60


# --- HU-011: casos límite de la variación rápida ------------------------------- Regla.

def variaciones(r):
    return [p for p in r.periodos if p.tipo in ("subida", "bajada")]


def rampa(desde, hasta, minutos, base_antes=6, base_despues=6):
    """Cambio lineal de `desde` a `hasta` en `minutos` (mediciones cada 5), con tramos planos antes y después."""
    pasos = minutos // 5
    rampa = [round(desde + (hasta - desde) * i / pasos) for i in range(pasos + 1)]
    return [desde] * base_antes + rampa + [hasta] * base_despues


def test_exactamente_60_mg_dl_en_60_minutos_es_variacion():
    r = calcular(serie(rampa(100, 160, 60)))
    v = variaciones(r)
    assert len(v) == 1 and v[0].tipo == "subida"
    assert (v[0].valor_inicio, v[0].valor_fin, v[0].duracion_min) == (100, 160, 60)


def test_59_mg_dl_en_60_minutos_no_es_variacion():
    assert variaciones(calcular(serie(rampa(100, 159, 60)))) == []


def test_60_mg_dl_en_65_minutos_no_es_variacion():
    # Ninguna ventana de 60 minutos alcanza los 60 mg/dL (como máximo 55).
    assert variaciones(calcular(serie(rampa(100, 160, 65)))) == []


def test_inicio_y_fin_en_los_extremos():
    # Meseta en 100, sube a 200 en 30 minutos y queda en 200: el período va de 100 a 200, no incluye las mesetas.
    r = calcular(serie(rampa(100, 200, 30)))
    v = variaciones(r)[0]
    local = lambda d: d.astimezone(ZoneInfo(ZONA)).strftime("%H:%M")
    assert (local(v.inicio), local(v.fin)) == ("10:30", "11:00")


def test_bajada_y_direccion():
    v = variaciones(calcular(serie(rampa(220, 140, 40))))
    assert len(v) == 1 and v[0].tipo == "bajada" and v[0].valor_extremo == 140


def test_subida_y_bajada_son_periodos_separados():
    valores = [100] * 4 + [130, 160, 190] + [190] * 2 + [160, 130, 100] + [100] * 4
    assert [p.tipo for p in variaciones(calcular(serie(valores)))] == ["subida", "bajada"]


def test_un_hueco_corta_la_variacion():
    # 100 a las 10:00 y 170 a las 10:40, sin mediciones en el medio (hueco > 10 minutos).
    df = pd.concat([serie([100, 100], "09:55"), serie([170, 170], "10:40")])
    assert variaciones(calcular(df)) == []


def test_ruido_no_corta_una_subida():
    # Pequeñas bajadas de 2 mg/dL en el medio no impiden detectar la subida de 100 a 175.
    valores = [100] * 4 + [115, 113, 130, 128, 150, 148, 175] + [175] * 4
    v = variaciones(calcular(serie(valores)))
    assert len(v) == 1 and (v[0].valor_inicio, v[0].valor_fin) == (100, 175)
