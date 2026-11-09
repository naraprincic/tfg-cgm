"""Pruebas de la configuración (HU-004), eventos manuales (HU-009), asociación temporal (HU-010), detalle del día (HU-012) e historial (HU-014)."""

import pytest
from sqlalchemy import select

from app.models import IndicadorDiario


@pytest.fixture
def sesion(cliente):
    cuenta = {"email": "nara@example.com", "contrasena": "Glucosa2026", "acepta_consentimiento": True}
    cliente.post("/auth/registro", json=cuenta)
    cliente.post("/auth/login", json={"email": cuenta["email"], "contrasena": cuenta["contrasena"]})
    return cliente


def importar_dia(cliente, dia="2026-10-15", valores=None, desde_hora=0):
    """Importa un día con una medición cada 5 minutos (por defecto, 120 mg/dL todo el día)."""
    valores = valores or [120] * (288 - desde_hora * 12)
    filas = []
    for i, v in enumerate(valores):
        minutos = desde_hora * 60 + i * 5
        filas.append(f"{dia} {minutos // 60:02d}:{minutos % 60:02d},{v}")
    texto = "fecha_hora,glucosa_mg_dl\n" + "\n".join(filas) + "\n"
    r = cliente.post("/importaciones", files={"archivo": ("dia.csv", texto.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    return r


# --- HU-007 integrada: la importación calcula los indicadores ----------------

def test_importar_calcula_indicadores_del_dia(sesion, db):
    importar_dia(sesion)
    ind = db.scalar(select(IndicadorDiario))
    assert ind.fecha.isoformat() == "2026-10-15"
    assert ind.tir == 100.0 and ind.cobertura == 100.0


# --- HU-004: configuración --------------------------------------------------

def test_limite_inferior_mayor_o_igual_al_superior(sesion):
    r = sesion.put("/configuracion", json={"rango_min": 180, "rango_max": 180})
    assert r.status_code == 422
    assert "menor que el superior" in r.json()["errores"][0]["mensaje"]
    assert sesion.get("/configuracion").json()["rango_min"] == 70  # se conservan los anteriores


def test_limites_fuera_de_40_a_300(sesion):
    r = sesion.put("/configuracion", json={"rango_min": 30, "rango_max": 320})
    assert r.status_code == 422
    assert {e["campo"] for e in r.json()["errores"]} == {"rango_min", "rango_max"}


def test_cambiar_el_rango_recalcula_los_dias(sesion, db):
    importar_dia(sesion, valores=[150] * 288)
    assert db.scalar(select(IndicadorDiario.tir_personal)) == 100.0
    r = sesion.put("/configuracion", json={"rango_min": 70, "rango_max": 140})
    assert r.status_code == 200 and r.json()["dias_recalculados"] == 1
    assert "recalcularon" in r.json()["mensaje"]
    db.expire_all()
    ind = db.scalar(select(IndicadorDiario))
    assert ind.tir_personal == 0.0   # 150 queda fuera del rango personal 70–140
    assert ind.tir == 100.0          # el consenso 70–180 no cambia


# --- HU-009: carga manual ---------------------------------------------------

def test_campos_minimos_del_evento(sesion):
    r = sesion.post("/eventos", json={})
    assert r.status_code == 422
    assert {"tipo", "descripcion", "fecha_hora"} <= {e["campo"] for e in r.json()["errores"]}


def test_dia_sin_datos_pide_confirmacion(sesion):
    evento = {"tipo": "comida", "descripcion": "Almuerzo", "fecha_hora": "2026-10-20T13:00"}
    r = sesion.post("/eventos", json=evento)
    assert r.status_code == 409 and "confirmar" in r.json()["detail"]
    r = sesion.post("/eventos", json={**evento, "confirmar_sin_datos": True})
    assert r.status_code == 201 and r.json()["hora"] == "13:00"


def test_unidad_que_no_corresponde_al_tipo(sesion):
    importar_dia(sesion)
    r = sesion.post("/eventos", json={"tipo": "insulina", "descripcion": "Rápida", "fecha_hora": "2026-10-15T08:00",
                                      "cantidad": 4, "unidad": "gramos"})
    assert r.status_code == 422 and "unidad no corresponde" in r.json()["errores"][0]["mensaje"]


def test_cantidad_imposible(sesion):
    importar_dia(sesion)
    r = sesion.post("/eventos", json={"tipo": "insulina", "descripcion": "Rápida", "fecha_hora": "2026-10-15T08:00",
                                      "cantidad": 600, "unidad": "unidades"})
    assert r.status_code == 422


# --- HU-010: asociación temporal --------------------------------------------

def evento(cliente, **datos):
    r = cliente.post("/eventos", json={"descripcion": "evento", **datos})
    assert r.status_code == 201, r.text


def detalle(cliente, dia="2026-10-15"):
    r = cliente.get(f"/dias/{dia}")
    assert r.status_code == 200, r.text
    return r.json()


def test_comida_informa_valor_previo_y_maximo_en_3_horas(sesion):
    # 100 hasta las 12:00, sube a 190 a las 13:30 y vuelve a 100.
    valores = [100] * 145 + [120, 150, 170, 190, 160, 130] + [100] * 137
    importar_dia(sesion, valores=valores)
    evento(sesion, tipo="comida", fecha_hora="2026-10-15T12:00", cantidad=1, unidad="porciones")
    a = detalle(sesion)["eventos"][0]["asociacion"]
    assert a["valor_previo"] == {"valor": 100, "hora": "12:00"}
    assert a["maximo_posterior"]["valor"] == 190
    assert a["ventana"] == "11:30 a 15:00"  # 30 min antes y 3 h después


def test_actividad_fisica_informa_valor_al_finalizar_minimo_y_variacion(sesion):
    importar_dia(sesion, valores=[150] * 204 + [140, 130, 120, 110, 100] + [100] * 79)
    evento(sesion, tipo="actividad_fisica", fecha_hora="2026-10-15T16:00", cantidad=40, unidad="minutos")
    a = detalle(sesion)["eventos"][0]["asociacion"]
    assert a["valor_al_finalizar"]["hora"] == "16:40"
    assert a["minimo_posterior"]["valor"] == 100
    assert a["variacion_2h"] == -50  # de 150 al finalizar a 100 dos horas después
    assert a["ventana"] == "16:00 a 18:40"  # del inicio a 2 h después de terminar


def test_evento_sin_mediciones_en_su_ventana_se_muestra_igual(sesion):
    importar_dia(sesion, valores=[120] * 60)  # solo hay datos de 00:00 a 05:00
    evento(sesion, tipo="sintoma", fecha_hora="2026-10-15T18:20")
    e = detalle(sesion)["eventos"][0]
    assert e["asociacion"]["sin_mediciones"] is True and e["descripcion"] == "evento"


def test_ventana_que_pasa_la_medianoche_usa_datos_del_dia_siguiente(sesion):
    importar_dia(sesion, dia="2026-10-15")
    importar_dia(sesion, dia="2026-10-16", valores=[200] * 288)
    evento(sesion, tipo="comida", fecha_hora="2026-10-15T23:00")
    dia15 = detalle(sesion, "2026-10-15")
    assert len(dia15["eventos"]) == 1  # el evento pertenece al día de su hora
    assert dia15["eventos"][0]["asociacion"]["maximo_posterior"]["valor"] == 200
    assert detalle(sesion, "2026-10-16")["eventos"] == []


# --- HU-012: detalle del día ------------------------------------------------

def test_detalle_del_dia_reune_curva_indicadores_y_eventos(sesion):
    importar_dia(sesion)
    evento(sesion, tipo="insulina", fecha_hora="2026-10-15T08:00", cantidad=4, unidad="unidades")
    d = detalle(sesion)
    assert len(d["puntos"]) == 288 and d["puntos"][0]["hora"] == "00:00"
    assert d["indicadores"]["tir"] == 100.0
    assert d["eventos"][0]["hora"] == "08:00"
    # Semáforo: todo el día en rango, sin horarios altos ni bajos.
    s = d["semaforo"]
    assert s["alto"] == [] and s["bajo"] == [] and s["en_rango"]["porcentaje"] == 100
    assert s["en_rango"]["horarios"][0]["desde"] == "00:00" and s["en_rango"]["horarios"][0]["hasta"] == "23:55"


def test_dia_sin_mediciones_lo_informa(sesion):
    r = sesion.get("/dias/2026-01-01")
    assert r.status_code == 404 and "No hay mediciones" in r.json()["detail"]


# --- HU-014: historial ------------------------------------------------------

def test_historial_ordenado_y_filtrado_por_periodo(sesion):
    for dia in ("2026-10-14", "2026-10-15", "2026-10-16"):
        importar_dia(sesion, dia=dia)
    h = sesion.get("/dias", params={"desde": "2026-10-15", "hasta": "2026-10-16"}).json()
    assert [d["fecha"] for d in h["dias"]] == ["2026-10-16", "2026-10-15"]
    assert all(d["tiene_resumen"] is False for d in h["dias"])


def test_periodo_sin_dias(sesion):
    h = sesion.get("/dias", params={"desde": "2020-01-01", "hasta": "2020-01-31"}).json()
    assert h["dias"] == []


def test_gmi_solo_con_14_dias_de_buena_cobertura(sesion):
    for d in range(1, 14):
        importar_dia(sesion, dia=f"2026-10-{d:02d}")
    assert sesion.get("/dias").json()["gmi"] is None  # 13 días
    importar_dia(sesion, dia="2026-10-14")
    h = sesion.get("/dias").json()
    assert h["gmi"] == 6.2  # 3,31 + 0,02392 × 120 = 6,18


# --- Aislamiento entre dos usuarios: días, eventos y resúmenes -------------

def test_un_usuario_no_ve_ni_borra_los_datos_de_otro(sesion):
    importar_dia(sesion)
    evento(sesion, tipo="comida", fecha_hora="2026-10-15T13:00")
    id_evento = sesion.get("/eventos", params={"fecha": "2026-10-15"}).json()[0]["id_evento"]
    sesion.post("/auth/logout")

    otra = {"email": "otra@example.com", "contrasena": "Glucosa2026", "acepta_consentimiento": True}
    sesion.post("/auth/registro", json=otra)
    sesion.post("/auth/login", json={"email": otra["email"], "contrasena": otra["contrasena"]})
    assert sesion.get("/dias").json()["dias"] == []
    assert sesion.get("/dias/2026-10-15").status_code == 404
    assert sesion.get("/eventos", params={"fecha": "2026-10-15"}).json() == []
    assert sesion.get("/eventos/recientes").json() == []
    assert sesion.delete(f"/eventos/{id_evento}").status_code == 404
    assert sesion.post("/dias/2026-10-15/resumen").status_code == 404

    # El evento de la primera persona sigue intacto.
    sesion.post("/auth/logout")
    sesion.post("/auth/login", json={"email": "nara@example.com", "contrasena": "Glucosa2026"})
    assert len(sesion.get("/eventos", params={"fecha": "2026-10-15"}).json()) == 1
