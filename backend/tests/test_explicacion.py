"""Pruebas del semáforo del día: horarios en rango, alta y baja, con los eventos registrados en ese horario o en las horas previas, y los redondeos de tiempo en palabras."""

from datetime import date

from app.analisis.explicacion import duracion, momento_del_dia, semaforo, tiempo_aproximado
from app.ia.resumen import DatosDia, EventoDatos, PeriodoDatos

DIA = DatosDia(
    fecha=date(2026, 10, 15), rango_min=70, rango_max=180, tir=95.8, tir_personal=95.8, tbr=2.1, tbr_nivel2=0.0,
    tar=2.1, tar_nivel2=0.0, glucosa_promedio=116.6, coeficiente_variacion=27.2, cobertura=100.0, parcial=False,
    mediciones=96,
    periodos=[PeriodoDatos("bajo", "05:30", "05:45", 15, 65), PeriodoDatos("bajo", "06:15", "06:30", 15, 68),
              PeriodoDatos("sobre", "12:45", "13:15", 30, 202)],
)


def test_redondeos():
    assert duracion(15) == "15 minutos" and duracion(30) == "media hora"
    assert duracion(75) == "1 hora y cuarto" and duracion(150) == "2 horas y media"
    assert tiempo_aproximado(1380) == "unas 23 horas" and tiempo_aproximado(28) == "media hora"
    assert momento_del_dia("05:30") == "a la madrugada" and momento_del_dia("21:00") == "a la noche"


CON_EVENTOS = DatosDia(**{**DIA.__dict__, "eventos": [
    EventoDatos("09:00", "comida", "desayuno"),
    EventoDatos("10:30", "insulina", "insulina rápida", 4, "U"),
    EventoDatos("12:30", "comida", "almuerzo"),
    EventoDatos("12:50", "actividad_fisica", "caminata", 30, "min"),
    EventoDatos("20:00", "comida", "cena"),
]})


def test_semaforo_horarios_alto_y_bajo():
    s = semaforo(CON_EVENTOS, "00:00", "23:55")
    assert [(h["desde"], h["hasta"], h["valor_extremo"]) for h in s["alto"]] == [("12:45", "13:15", 202)]
    assert [h["desde"] for h in s["bajo"]] == ["05:30", "06:15"]
    assert s["alto"][0]["cuando"] == "al mediodía" and s["alto"][0]["duracion"] == "media hora"


def test_semaforo_eventos_en_el_horario_o_en_las_3_horas_previas():
    eventos = semaforo(CON_EVENTOS, "00:00", "23:55")["alto"][0]["eventos"]
    # 09:00 queda a más de 3 horas de las 12:45; la cena es posterior.
    assert [(e["hora"], e["momento"]) for e in eventos] == [("10:30", "antes"), ("12:30", "antes"), ("12:50", "durante")]
    assert semaforo(CON_EVENTOS, "00:00", "23:55")["bajo"][0]["eventos"] == []


def test_semaforo_en_rango_es_el_resto_del_dia():
    s = semaforo(CON_EVENTOS, "00:00", "23:55")
    assert [(h["desde"], h["hasta"]) for h in s["en_rango"]["horarios"]] == [
        ("00:00", "05:30"), ("05:45", "06:15"), ("06:30", "12:45"), ("13:15", "23:55")]
    d = DatosDia(**{**DIA.__dict__, "periodos": [PeriodoDatos("bajo", "05:30", "05:45", 15, 65),
                                                  PeriodoDatos("bajo", "05:55", "06:15", 20, 66)]})
    # 05:45 a 05:55 dura menos de 15 minutos: no se muestra como tramo en rango.
    assert [h["desde"] for h in semaforo(d, "00:00", "23:55")["en_rango"]["horarios"]] == ["00:00", "06:15"]
    assert s["en_rango"]["porcentaje"] == 96 and s["en_rango"]["tiempo"] == "unas 23 horas"


def test_semaforo_dia_sin_momentos_fuera_de_rango():
    d = DatosDia(**{**DIA.__dict__, "periodos": [], "tir_personal": 100.0})
    s = semaforo(d, "07:10", "22:40")
    assert s["alto"] == [] and s["bajo"] == []
    assert [(h["desde"], h["hasta"]) for h in s["en_rango"]["horarios"]] == [("07:10", "22:40")]


def test_semaforo_en_orden_de_hora():
    d = DatosDia(**{**DIA.__dict__, "periodos": [PeriodoDatos("sobre", "16:50", "18:50", 120, 227),
                                                  PeriodoDatos("sobre", "08:00", "08:30", 30, 190)]})
    assert [h["desde"] for h in semaforo(d, "00:00", "23:55")["alto"]] == ["08:00", "16:50"]
