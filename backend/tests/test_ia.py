"""Pruebas de la parte de inteligencia artificial: registro en lenguaje natural (HU-008) y resumen diario (HU-013)."""

from datetime import date, time

import pytest
from sqlalchemy import select

from app.config import settings
from app.ia import cliente, extraccion, resumen
from app.models import Evento, ResumenDiario


def ev(tipo, descripcion, cantidad=None, unidad=None, hora=None, estimada=False, dia=0):
    return {"tipo": tipo, "descripcion": descripcion, "cantidad": cantidad, "unidad": unidad,
            "hora": hora, "hora_estimada": estimada, "dia_relativo": dia}


class ModeloSimulado:
    """Reemplaza a la API: devuelve las respuestas indicadas, en orden, y registra los pedidos."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.pedidos = []

    def __call__(self, sistema, usuario, nombre, esquema):
        self.pedidos.append(usuario)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


@pytest.fixture
def con_ia(monkeypatch):
    """Simula que hay una clave configurada y permite fijar las respuestas del modelo."""
    monkeypatch.setattr(settings, "openai_api_key", "sk-prueba")

    def fijar(*respuestas):
        modelo = ModeloSimulado(*respuestas)
        monkeypatch.setattr(cliente, "llamar_json", modelo)
        return modelo

    return fijar


@pytest.fixture
def sin_ia(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)


@pytest.fixture
def sesion(cliente):
    cuenta = {"email": "nara@example.com", "contrasena": "Glucosa2026", "acepta_consentimiento": True}
    cliente.post("/auth/registro", json=cuenta)
    cliente.post("/auth/login", json={"email": cuenta["email"], "contrasena": cuenta["contrasena"]})
    return cliente


def importar_dia(cliente, dia="2026-10-15", valores=None):
    valores = valores or [120] * 288
    filas = [f"{dia} {(i * 5) // 60:02d}:{(i * 5) % 60:02d},{v}" for i, v in enumerate(valores)]
    texto = "fecha_hora,glucosa_mg_dl\n" + "\n".join(filas) + "\n"
    assert cliente.post("/importaciones", files={"archivo": ("d.csv", texto.encode(), "text/csv")}).status_code == 201


TEXTO = "Almorcé milanesa con puré a las 13 menos diez, me puse 6 unidades de rápida y a las 4 de la tarde salí a caminar como 40 minutos"
RESPUESTA_FIGURA_8 = {"eventos": [
    ev("comida", "Milanesa con puré", None, None, "12:50"),
    ev("insulina", "Insulina rápida", 6, "unidades", None),
    ev("actividad_fisica", "Caminata", 40, "minutos", "16:00"),
]}


# HU-008: registro en lenguaje natural.

def test_varios_eventos_y_hora_propuesta(con_ia):
    con_ia(RESPUESTA_FIGURA_8)
    b = extraccion.interpretar(TEXTO, date(2026, 10, 15))
    assert [x.tipo for x in b] == ["comida", "insulina", "actividad_fisica"]   # criterio 1
    assert b[0].fecha_hora.strftime("%H:%M") == "12:50" and not b[0].hora_propuesta  # criterio 2
    # La insulina no tiene hora: se propone la del almuerzo y se marca como propuesta.
    assert b[1].fecha_hora.strftime("%H:%M") == "12:50" and b[1].hora_propuesta and b[1].hora_aproximada
    assert "no indica la hora" in b[1].advertencias[0]


def test_sin_hora_ni_eventos_vecinos_se_propone_la_hora_actual(con_ia):
    con_ia({"eventos": [ev("comida", "Banana")]})
    b = extraccion.interpretar("comí una banana", date(2026, 10, 15), hora_actual=time(17, 30))
    assert b[0].fecha_hora.strftime("%H:%M") == "17:30" and b[0].hora_propuesta


def test_ayer_corresponde_al_dia_anterior(con_ia):
    con_ia({"eventos": [ev("insulina", "Insulina lenta", 18, "unidades", "23:00", dia=-1)]})
    b = extraccion.interpretar("anoche a las 23 me puse 18 de lenta", date(2026, 10, 15))
    assert b[0].fecha_hora.date() == date(2026, 10, 14)


def test_respuesta_con_errores_se_pide_una_segunda_vez(con_ia):
    modelo = con_ia(
        {"eventos": [ev("insulina", "Insulina rápida", 4, "gramos", "08:00")]},  # unidad incorrecta
        {"eventos": [ev("insulina", "Insulina rápida", 4, "unidades", "08:00")]},
    )
    b = extraccion.interpretar("me puse 4 de rápida a las 8", date(2026, 10, 15))
    assert len(modelo.pedidos) == 2 and "no corresponde" in modelo.pedidos[1]
    assert b[0].unidad == "unidades"


def test_dos_respuestas_con_errores_ofrecen_carga_manual(con_ia, sesion):
    importar_dia(sesion)
    malo = {"eventos": [ev("insulina", "Rápida", 4, "gramos", "08:00")]}
    con_ia(malo, malo)
    r = sesion.post("/eventos/interpretar", json={"texto": "me puse 4 de rápida", "fecha": "2026-10-15"})
    assert r.status_code == 422 and "cargar los eventos manualmente" in r.json()["detail"]


def test_servicio_no_disponible_conserva_el_texto(sin_ia, sesion):
    r = sesion.post("/eventos/interpretar", json={"texto": "almorcé a las 13", "fecha": "2026-10-15"})
    assert r.status_code == 503 and "Tu texto se conservó" in r.json()["detail"]  # criterio 5


def test_cantidad_imposible_queda_marcada_para_revision(con_ia):
    con_ia({"eventos": [ev("insulina", "Insulina", 600, "unidades", "08:00")]})
    b = extraccion.interpretar("me puse 600 unidades", date(2026, 10, 15))
    assert "parece incorrecta" in b[0].advertencias[0]


def test_borradores_no_se_usan_hasta_confirmarlos(con_ia, sesion, db):
    importar_dia(sesion)
    con_ia(RESPUESTA_FIGURA_8)
    r = sesion.post("/eventos/interpretar", json={"texto": TEXTO, "fecha": "2026-10-15"})
    assert r.status_code == 200
    borradores = r.json()["borradores"]
    assert len(borradores) == 3 and borradores[1]["hora_propuesta"]
    # Criterio 3: todavía no aparecen en el día.
    assert sesion.get("/dias/2026-10-15").json()["eventos"] == []
    assert sesion.get("/eventos", params={"fecha": "2026-10-15"}).json() == []

    # Criterio 4: se confirman con correcciones (la insulina a las 12:45).
    a_confirmar = []
    for b in borradores:
        hora = "12:45" if b["tipo"] == "insulina" else b["hora"]
        a_confirmar.append({"id_evento": b["id_evento"], "tipo": b["tipo"], "descripcion": b["descripcion"],
                            "fecha_hora": f"2026-10-15T{hora}", "hora_aproximada": False,
                            "cantidad": b["cantidad"], "unidad": b["unidad"]})
    assert sesion.post("/eventos/confirmar", json={"eventos": a_confirmar}).status_code == 200
    detalle = sesion.get("/dias/2026-10-15").json()
    assert [e["hora"] for e in detalle["eventos"]] == ["12:45", "12:50", "16:00"]
    # El texto original queda guardado junto a cada evento.
    assert all(e.texto_original == TEXTO for e in db.scalars(select(Evento)))


def test_confirmar_valida_igual_que_la_carga_manual(con_ia, sesion):
    importar_dia(sesion)
    con_ia({"eventos": [ev("insulina", "Insulina", 600, "unidades", "08:00")]})
    b = sesion.post("/eventos/interpretar", json={"texto": "600 unidades", "fecha": "2026-10-15"}).json()["borradores"][0]
    datos = {"id_evento": b["id_evento"], "tipo": "insulina", "descripcion": "Insulina",
             "fecha_hora": "2026-10-15T08:00", "cantidad": 600, "unidad": "unidades"}
    assert sesion.post("/eventos/confirmar", json={"eventos": [datos]}).status_code == 422
    datos["cantidad"] = 6
    assert sesion.post("/eventos/confirmar", json={"eventos": [datos]}).status_code == 200


def test_descartar_borradores(con_ia, sesion, db):
    importar_dia(sesion)
    con_ia(RESPUESTA_FIGURA_8)
    ids = [b["id_evento"] for b in sesion.post("/eventos/interpretar", json={"texto": TEXTO, "fecha": "2026-10-15"}).json()["borradores"]]
    assert sesion.post("/eventos/descartar", json={"ids": ids}).status_code == 204
    assert {e.estado for e in db.scalars(select(Evento))} == {"descartado"}
    assert sesion.get("/dias/2026-10-15").json()["eventos"] == []


def test_texto_sin_eventos(con_ia, sesion):
    con_ia({"eventos": []})
    r = sesion.post("/eventos/interpretar", json={"texto": "hola", "fecha": "2026-10-15"})
    assert r.status_code == 422 and "No se encontraron eventos" in r.json()["detail"]


# HU-013: resumen diario – verificación (pruebas unitarias)

DATOS = resumen.DatosDia(
    fecha=date(2026, 10, 31), rango_min=70, rango_max=180, tir=87.8, tir_personal=87.8, tbr=3.8, tbr_nivel2=0.0,
    tar=8.3, tar_nivel2=0.0, glucosa_promedio=120.3, coeficiente_variacion=32.7, cobertura=100.0, parcial=False,
    mediciones=284,
    periodos=[resumen.PeriodoDatos("bajo", "04:00", "04:55", 55, 56),
              resumen.PeriodoDatos("sobre", "16:50", "18:50", 120, 227)],
    eventos=[resumen.EventoDatos("13:00", "comida", "Almuerzo: milanesa con puré", 1, "porciones"),
             resumen.EventoDatos("16:00", "actividad_fisica", "Caminata", 40, "minutos")],
)

TEXTO_CORRECTO = (
    "El sábado 31 de octubre tus valores estuvieron dentro del rango de 70 a 180 mg/dL el 88 % del tiempo, "
    "con un promedio de 120 mg/dL y una variabilidad del 32,7 %. Hubo un período por debajo de tu rango de 04:00 a 04:55, "
    "con un mínimo de 56 mg/dL, y otro por encima de 16:50 a 18:50, con un máximo de 227 mg/dL, que comenzó después de la "
    "caminata de las 16:00 que registraste. Estas coincidencias en el tiempo no indican por sí solas la causa de los cambios."
)


def test_texto_correcto_se_aprueba():
    assert resumen.verificar(TEXTO_CORRECTO, DATOS) == []


def test_numero_que_no_coincide():
    problemas = resumen.verificar(TEXTO_CORRECTO.replace("227", "235"), DATOS)
    assert any("235" in p for p in problemas)


def test_periodo_omitido():
    texto = TEXTO_CORRECTO.replace("de 04:00 a 04:55", "a la madrugada")
    assert any("04:00" in p for p in resumen.verificar(texto, DATOS))


@pytest.mark.parametrize("frase", [
    "El aumento fue porque almorzaste milanesa.",
    "La caminata provocó la baja.",
    "Deberías ajustar la insulina.",
    "Te recomiendo comer menos harinas.",
    "Tuviste un buen control.",
    "Conviene que hables con tu médico.",
])
def test_causas_diagnosticos_y_recomendaciones_se_rechazan(frase):
    assert resumen.verificar(TEXTO_CORRECTO + " " + frase, DATOS)


@pytest.mark.parametrize("frase", [
    "La subida fue por la comida.",
    "Fue un día normal.",
    "La caminata influyó en la baja.",
    "Fue una consecuencia del almuerzo.",
    "La subida fue por la milanesa del almuerzo.",
    "Subió por haber comido tarde.",
    "No hubo eventos, así que no podemos saber qué pudo influir en los cambios.",
    "Hoy estuviste en rango el 88 % del tiempo.",
])
def test_otras_causas_y_valoraciones_se_rechazan(frase):
    assert resumen.verificar(TEXTO_CORRECTO + " " + frase, DATOS)


def test_por_debajo_y_por_encima_no_se_confunden_con_una_causa():
    texto = TEXTO_CORRECTO + " A la madrugada bajó por debajo de tu rango y a la tarde subió por encima."
    assert not any("no permitida" in p for p in resumen.verificar(texto, DATOS))


# Momentos del día: períodos agrupados y eventos cercanos (sin IA)

DIA_16 = resumen.DatosDia(
    fecha=date(2026, 10, 16), rango_min=70, rango_max=180, tir=88.5, tir_personal=88.5, tbr=3.5, tbr_nivel2=0.0,
    tar=8.0, tar_nivel2=0.0, glucosa_promedio=123.1, coeficiente_variacion=29.5, cobertura=100.0, parcial=False,
    mediciones=288,
    periodos=[resumen.PeriodoDatos("subida", "11:25", "12:40", 75, 193, 112, 193),
              resumen.PeriodoDatos("sobre", "12:20", "12:55", 35, 193),
              resumen.PeriodoDatos("sobre", "15:40", "15:55", 15, 183),
              resumen.PeriodoDatos("bajada", "22:55", "23:55", 60, 57, 125, 57)],
    eventos=[resumen.EventoDatos("07:30", "comida", "Desayuno: tostadas con queso"),
             resumen.EventoDatos("12:35", "insulina", "Insulina rápida", 5, "unidades"),
             resumen.EventoDatos("12:40", "comida", "Almuerzo: ensalada y pollo")],
)


def test_periodos_superpuestos_forman_un_solo_momento():
    momentos, _ = resumen.agrupar_momentos(DIA_16)
    assert [(m.desde, m.hasta, len(m.periodos)) for m in momentos] == [("11:25", "12:55", 2), ("15:40", "15:55", 1),
                                                                         ("22:55", "23:55", 1)]


def test_cada_evento_se_cuenta_en_un_solo_momento():
    momentos, otros = resumen.agrupar_momentos(DIA_16)
    # El almuerzo de las 12:40 queda en el momento del mediodía y no se repite en el de las 15:40.
    assert [(e.hora, r) for e, r in momentos[0].eventos_cercanos] == [("12:35", "durante"), ("12:40", "durante")]
    assert momentos[1].eventos_cercanos == []
    assert [e.hora for e in otros] == ["07:30"]


def test_porcentajes_redondeados_suman_lo_mismo_que_los_reales():
    assert sum(resumen.porcentajes_redondeados(DIA_16)) == 100      # 88,5 + 3,5 + 8 (sin redondear daría 88 + 4 + 8)
    assert resumen.porcentajes_redondeados(DATOS) == (88, 4, 8)


def test_plantilla_cuenta_los_momentos_juntos_y_destaca_los_eventos_cercanos():
    texto = resumen.plantilla(DATOS)
    assert "Poco antes habías registrado actividad física: caminata (40 minutos) a las 16:00" in texto
    assert texto.count("16:00") == 1 and "no muestra por sí solo" in texto
    texto = resumen.plantilla(DIA_16)
    assert "subió rápido de 112 a 193 mg/dL entre las 11:25 y las 12:40 y estuvo por encima de tu rango de 12:20 a 12:55" in texto
    assert texto.count("12:40") == 2 and texto.count("almuerzo") == 1   # la hora del fin de la subida y el evento
    assert resumen.verificar(texto, DIA_16) == []


def test_datos_para_el_modelo_agrupan_momentos_y_eventos():
    texto = resumen.datos_como_texto(DIA_16)
    assert "Momento 1, a la mañana, de 11:25 a 12:55 (horas de inicio que el texto tiene que nombrar: 11:25, 12:20):" in texto
    assert "evento cercano (durante el momento): 12:40" in texto
    assert "en rango 89 %, por debajo 3 %, por encima 8 %" in texto
    assert "Otros eventos registrados" in texto and "07:30" in texto


def test_los_motivos_de_rechazo_no_se_repiten(monkeypatch):
    # Si los dos intentos fallan por lo mismo, el motivo aparece una sola vez.
    texto = "El viernes 16 tu glucosa estuvo en rango el 88 % del tiempo, promedio 123 mg/dL y variabilidad 30 %."
    monkeypatch.setattr(resumen.cliente, "disponible", lambda: True)
    monkeypatch.setattr(resumen.cliente, "llamar_json", lambda *a, **k: {"resumen": texto})
    r = resumen.generar(DIA_16)
    assert r.estado == "plantilla"
    assert len(r.observaciones) == len(set(r.observaciones))


def test_la_plantilla_pasa_su_propia_verificacion():
    assert resumen.verificar(resumen.plantilla(DATOS), DATOS) == []


def test_los_datos_enviados_no_incluyen_identificacion():
    texto = resumen.datos_como_texto(DATOS)
    assert "@" not in texto and "nara" not in texto.lower()


# HU-013: resumen diario – generación y versiones (API)

def resumen_del_modelo(texto):
    return {"resumen": texto}


def test_sin_ia_se_usa_la_plantilla_identificada(sin_ia, sesion):
    importar_dia(sesion)
    r = sesion.post("/dias/2026-10-15/resumen").json()
    assert r["estado_verificacion"] == "plantilla" and r["modelo_utilizado"] == "plantilla automática"
    assert "no constituye un diagnóstico" in r["aviso"]


def test_resumen_aprobado(con_ia, sesion):
    importar_dia(sesion)
    texto = ("El jueves 15 de octubre tus valores estuvieron dentro del rango de 70 a 180 mg/dL el 100 % del tiempo, "
             "con un promedio de 120 mg/dL y una variabilidad del 0 %. No hubo períodos fuera de tu rango.")
    con_ia(resumen_del_modelo(texto))
    r = sesion.post("/dias/2026-10-15/resumen").json()
    assert r["estado_verificacion"] == "aprobado" and r["texto"] == texto
    assert r["modelo_utilizado"] == "gpt-4o-2024-08-06" and r["version"] == 1


def test_numero_incorrecto_se_regenera_una_vez(con_ia, sesion):
    importar_dia(sesion)
    malo = "El jueves 15 de octubre estuviste en rango el 93 % del tiempo, con un promedio de 120 mg/dL y una variabilidad del 0 %."
    bueno = malo.replace("93", "100")
    modelo = con_ia(resumen_del_modelo(malo), resumen_del_modelo(bueno))
    r = sesion.post("/dias/2026-10-15/resumen").json()
    assert len(modelo.pedidos) == 2 and "93" in modelo.pedidos[1]
    assert r["estado_verificacion"] == "aprobado" and r["texto"] == bueno
    assert any("93" in o for o in r["observaciones"])


def test_dos_textos_rechazados_usan_la_plantilla(con_ia, sesion):
    importar_dia(sesion)
    causal = resumen_del_modelo("El jueves 15 de octubre estuviste en rango el 100 % del tiempo porque comiste bien y caminaste.")
    con_ia(causal, causal)
    r = sesion.post("/dias/2026-10-15/resumen").json()
    assert r["estado_verificacion"] == "plantilla"
    assert any("no permitida" in o for o in r["observaciones"])


def test_servicio_caido_usa_la_plantilla(con_ia, sesion):
    importar_dia(sesion)
    con_ia(cliente.ServicioNoDisponible("sin conexión"))
    assert sesion.post("/dias/2026-10-15/resumen").json()["estado_verificacion"] == "plantilla"


def test_versiones_y_vigente(sin_ia, sesion, db):
    importar_dia(sesion)
    sesion.post("/dias/2026-10-15/resumen")
    segunda = sesion.post("/dias/2026-10-15/resumen").json()
    assert segunda["version"] == 2 and segunda["motivo_generacion"] == "regeneración solicitada"
    versiones = sesion.get("/dias/2026-10-15/resumenes").json()
    assert [(v["version"], v["vigente"]) for v in versiones] == [(2, True), (1, False)]
    assert sesion.get("/dias/2026-10-15").json()["resumen"]["version"] == 2


def test_cambios_en_los_datos_marcan_el_resumen_desactualizado(sin_ia, sesion, db):
    importar_dia(sesion, valores=[120] * 200)  # día parcial
    sesion.post("/dias/2026-10-15/resumen")
    # Se suman las mediciones que faltaban: cambian los indicadores (criterio 4).
    importar_dia(sesion, valores=[120] * 200 + [200] * 88)
    assert sesion.get("/dias").json()["dias"][0]["estado_resumen"] == "desactualizado"
    nuevo = sesion.post("/dias/2026-10-15/resumen").json()
    assert nuevo["motivo_generacion"] == "actualización de datos" and nuevo["estado_verificacion"] == "plantilla"


def test_un_evento_nuevo_marca_el_resumen_desactualizado(sin_ia, sesion, db):
    importar_dia(sesion)
    sesion.post("/dias/2026-10-15/resumen")
    sesion.post("/eventos", json={"tipo": "comida", "descripcion": "Almuerzo", "fecha_hora": "2026-10-15T13:00"})
    assert db.scalar(select(ResumenDiario.estado_verificacion).where(ResumenDiario.vigente.is_(True))) == "desactualizado"


def test_omitir_indicadores_principales_se_rechaza():
    texto = ("El sábado 31 de octubre hubo un período por debajo de tu rango de 04:00 a 04:55, con un mínimo de 56 mg/dL, "
             "y otro por encima de 16:50 a 18:50, con un máximo de 227 mg/dL.")
    problemas = resumen.verificar(texto, DATOS)
    assert any("tiempo en rango" in p for p in problemas)
    assert any("promedio" in p for p in problemas)
    assert any("variabilidad" in p for p in problemas)


def test_las_instrucciones_no_inventan_cantidades():
    # Corrección del director: la referencia no debe introducir cantidades ni duraciones que el texto no aporta.
    assert "no son 2 porciones" in extraccion.INSTRUCCIONES
    assert "no cuánto duró" in extraccion.INSTRUCCIONES


# --- Demo pública: tope diario de pedidos al modelo ---------------------------

def test_limite_diario_corta_antes_de_llamar_al_modelo(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-prueba")
    monkeypatch.setattr(settings, "limite_ia_diario", 2)
    monkeypatch.setitem(cliente._uso_diario, "fecha", None)
    llamadas = []

    class Falso:
        def __init__(self, **_):
            self.chat = self
            self.completions = self

        def create(self, **_):
            llamadas.append(1)
            raise openai.OpenAIError("servicio caído")

    import openai
    monkeypatch.setattr(openai, "OpenAI", Falso)
    for _ in range(2):
        with pytest.raises(cliente.ServicioNoDisponible):
            cliente.llamar_json("s", "u", "x", {})
    with pytest.raises(cliente.ServicioNoDisponible, match="límite diario"):
        cliente.llamar_json("s", "u", "x", {})
    assert len(llamadas) == 2


def test_direccion_de_la_base_en_la_nube_usa_psycopg():
    from app.config import Settings
    assert Settings(database_url="postgres://u:c@host/db").database_url == "postgresql+psycopg://u:c@host/db"
    assert Settings(database_url="postgresql://u:c@host/db?sslmode=require").database_url.startswith("postgresql+psycopg://")
