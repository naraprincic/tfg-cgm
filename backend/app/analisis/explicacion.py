"""Semáforo del día en lenguaje cotidiano: en qué horarios la glucosa estuvo dentro, por encima o por debajo del rango personal, y qué eventos se registraron en esos horarios."""

from dataclasses import asdict, dataclass, field

from app.ia.resumen import HORAS_PREVIAS, DatosDia, EventoDatos, PeriodoDatos, momento_del_dia


def duracion(minutos: float) -> str:
    """15 -> "15 minutos"; 30 -> "media hora"; 75 -> "1 hora y cuarto"; 150 -> "2 horas y media"."""
    minutos = int(round(minutos / 5) * 5)
    if minutos < 60:
        return "media hora" if minutos == 30 else f"{max(minutos, 5)} minutos"
    horas, resto = divmod(minutos, 60)
    texto = "1 hora" if horas == 1 else f"{horas} horas"
    extra = {0: "", 15: " y cuarto", 30: " y media", 45: " y tres cuartos"}
    if resto in extra:
        return texto + extra[resto]
    return f"{texto} y {resto} minutos"


def tiempo_aproximado(minutos: float) -> str:
    """Tiempo redondeado para leer de un vistazo: "unos 30 minutos", "unas 23 horas", "unas 2 horas y media"."""
    if minutos < 55:
        redondeado = max(5, int(round(minutos / 5) * 5))
        return "media hora" if redondeado == 30 else f"unos {redondeado} minutos"
    medias_horas = round(minutos / 30)
    horas, media = divmod(medias_horas, 2)
    if horas == 1 and not media:
        return "1 hora"
    base = "1 hora" if horas == 1 else f"unas {horas} horas"
    return base + (" y media" if media else "")


# Semáforo del día: verde (en tu rango), amarillo (alta) y rojo (baja)

MINUTOS_MINIMOS_EN_RANGO = 15


@dataclass
class EventoEnHorario:
    hora: str
    tipo: str
    descripcion: str
    cantidad: float | None
    unidad: str | None
    momento: str  # "antes" | "durante"


@dataclass
class Horario:
    desde: str
    hasta: str
    cuando: str            # "al mediodía"
    duracion: str          # "media hora"
    valor_extremo: int | None = None
    eventos: list[EventoEnHorario] = field(default_factory=list)


def _minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def _hora(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _eventos_del_horario(p: PeriodoDatos, eventos: list[EventoDatos]) -> list[EventoEnHorario]:
    desde, hasta = _minutos(p.desde), _minutos(p.hasta)
    elegidos = []
    for e in eventos:
        m = _minutos(e.hora)
        if desde - HORAS_PREVIAS * 60 <= m <= hasta:
            elegidos.append(EventoEnHorario(e.hora, e.tipo, e.descripcion, e.cantidad, e.unidad,
                                            "antes" if m < desde else "durante"))
    return sorted(elegidos, key=lambda x: x.hora)


def _horarios_fuera(d: DatosDia, tipo: str) -> list[Horario]:
    return [
        Horario(p.desde, p.hasta, momento_del_dia(p.desde), duracion(p.duracion_min), p.valor_extremo,
                _eventos_del_horario(p, d.eventos))
        for p in sorted((p for p in d.periodos if p.tipo == tipo), key=lambda p: p.desde)
    ]


def _horarios_en_rango(fuera: list[Horario], primera: str, ultima: str) -> list[Horario]:
    """Los tramos entre la primera y la última medición que no están en ningún horario alto o bajo."""
    tramos, cursor = [], _minutos(primera)
    for h in sorted(fuera, key=lambda h: h.desde):
        inicio, fin = _minutos(h.desde), _minutos(h.hasta)
        if inicio > cursor:
            tramos.append((cursor, inicio))
        cursor = max(cursor, fin)
    if _minutos(ultima) > cursor:
        tramos.append((cursor, _minutos(ultima)))
    return [Horario(_hora(a), _hora(b), momento_del_dia(_hora(a)), duracion(b - a))
            for a, b in tramos if b - a >= MINUTOS_MINIMOS_EN_RANGO]


def semaforo(d: DatosDia, primera: str, ultima: str) -> dict:
    """Arma los tres recuadros. `primera` y `ultima` son las horas de la primera y la última medición."""
    minutos_con_datos = d.cobertura / 100 * 1440
    alto = _horarios_fuera(d, "sobre")
    bajo = _horarios_fuera(d, "bajo")
    return {
        "rango_min": d.rango_min,
        "rango_max": d.rango_max,
        "horas_previas": HORAS_PREVIAS,
        "en_rango": {
            "porcentaje": round(d.tir_personal),
            "tiempo": tiempo_aproximado(d.tir_personal / 100 * minutos_con_datos),
            "horarios": [asdict(h) for h in _horarios_en_rango(alto + bajo, primera, ultima)],
        },
        "alto": [asdict(h) for h in alto],
        "bajo": [asdict(h) for h in bajo],
    }
