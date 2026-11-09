"""Estructuración de eventos escritos en lenguaje natural (HU-008)."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.ia import cliente

TIPOS = ["comida", "insulina", "actividad_fisica", "sintoma", "otro"]
UNIDADES_POR_TIPO = {
    "comida": {"gramos": 2000, "porciones": 20},
    "insulina": {"unidades": 100},
    "actividad_fisica": {"minutos": 600},
    "sintoma": {},
    "otro": {"minutos": 600},
}

ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["eventos"],
    "properties": {
        "eventos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tipo", "descripcion", "cantidad", "unidad", "hora", "hora_estimada", "dia_relativo"],
                "properties": {
                    "tipo": {"type": "string", "enum": TIPOS},
                    "descripcion": {"type": "string"},
                    "cantidad": {"type": ["number", "null"]},
                    "unidad": {"type": ["string", "null"], "enum": ["gramos", "porciones", "unidades", "minutos", None]},
                    "hora": {"type": ["string", "null"], "description": "HH:MM en formato de 24 horas, o null si el texto no indica la hora"},
                    "hora_estimada": {"type": "boolean"},
                    "dia_relativo": {"type": "integer", "description": "0 = el día de referencia, -1 = el día anterior"},
                },
            },
        }
    },
}

INSTRUCCIONES = """Sos un asistente que convierte en datos estructurados lo que una persona con diabetes escribe sobre su día.
Tu única tarea es identificar los acontecimientos y completar los campos. No des consejos, no interpretes la glucosa, no indiques dosis.

Reglas:
- Generá un evento por cada acontecimiento mencionado (comidas, aplicaciones de insulina, actividad física, síntomas u otros).
- tipo: "comida", "insulina", "actividad_fisica", "sintoma" u "otro" (cualquier cosa que no encaje en los anteriores, por ejemplo una consulta médica).
- descripcion: breve y en español, sin cantidades (por ejemplo "Milanesa con puré", "Insulina rápida", "Caminata", "Mareo y temblor"). Para la insulina indicá si es rápida o lenta cuando el texto lo diga.
- cantidad y unidad: SOLO si el texto dice explícitamente una cantidad en una unidad admitida. Unidades admitidas: comida -> "porciones" o "gramos"; insulina -> "unidades"; actividad física -> "minutos". No inventes ni estandarices cantidades: "dos tostadas" no son 2 porciones (cantidad null; la descripción conserva "Dos tostadas"); un plato sin cantidad no es 1 porción. "4 de rápida" son 4 unidades. "Caminé media hora" es una duración de 30 minutos, pero "corrí media hora después de cenar" indica cuándo empezó, no cuánto duró: la duración queda null. Los síntomas no llevan cantidad. Si no hay cantidad explícita, usá null en cantidad y en unidad. Copiá la cantidad tal como aparece, aunque parezca imposible.
- hora: en formato HH:MM de 24 horas. Interpretá expresiones coloquiales: "13 menos diez" = 12:50, "a las 4 de la tarde" = 16:00, "21 hs" = 21:00, "a las 8 de la noche" = 20:00.
- Si el texto no dice la hora, poné hora null. Si da una referencia vaga ("a la tarde", "después de cenar"), poné una hora aproximada razonable y hora_estimada true. Si la hora es explícita, hora_estimada false.
- dia_relativo: 0 si ocurrió el día de referencia; -1 si dice "ayer" o "anoche" (anoche después de las 20 h corresponde al día anterior).
- Si el texto no describe ningún acontecimiento, devolvé una lista vacía."""

HORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class InterpretacionFallida(Exception):
    """El modelo respondió dos veces con errores: se ofrece la carga manual."""


@dataclass
class Borrador:
    tipo: str
    descripcion: str
    cantidad: float | None
    unidad: str | None
    fecha_hora: datetime  # hora local (sin zona)
    hora_aproximada: bool
    hora_propuesta: bool  # el texto no tenía hora: la propuso el sistema
    advertencias: list[str] = field(default_factory=list)


def _errores_de_estructura(eventos: list[dict]) -> list[str]:
    """Errores que justifican pedirle al modelo una segunda respuesta."""
    errores = []
    for i, e in enumerate(eventos, start=1):
        if e["tipo"] not in TIPOS:
            errores.append(f"Evento {i}: tipo no admitido.")
        if not e["descripcion"].strip():
            errores.append(f"Evento {i}: la descripción está vacía.")
        if (e["cantidad"] is None) != (e["unidad"] is None):
            errores.append(f"Evento {i}: cantidad y unidad deben indicarse juntas o ser ambas null.")
        if e["unidad"] is not None and e["unidad"] not in UNIDADES_POR_TIPO.get(e["tipo"], {}):
            errores.append(f"Evento {i}: la unidad «{e['unidad']}» no corresponde al tipo «{e['tipo']}».")
        if e["hora"] is not None and not HORA.match(e["hora"]):
            errores.append(f"Evento {i}: la hora debe tener el formato HH:MM.")
        if e["dia_relativo"] not in (0, -1):
            errores.append(f"Evento {i}: dia_relativo debe ser 0 o -1.")
    return errores


def _pedir(texto: str, fecha_referencia: date, correccion: str | None = None) -> list[dict]:
    mensaje = f"Día de referencia: {fecha_referencia.isoformat()}.\nTexto de la persona: «{texto}»"
    if correccion:
        mensaje += f"\n\nTu respuesta anterior tenía estos errores, corregilos: {correccion}"
    return cliente.llamar_json(INSTRUCCIONES, mensaje, "eventos_cotidianos", ESQUEMA)["eventos"]


def interpretar(texto: str, fecha_referencia: date, hora_actual: time | None = None) -> list[Borrador]:
    """Devuelve los borradores interpretados."""
    try:
        eventos = _pedir(texto, fecha_referencia)
        errores = _errores_de_estructura(eventos)
    except ValueError as error:  # JSON inválido
        eventos, errores = [], [str(error)]
    if errores:
        try:
            eventos = _pedir(texto, fecha_referencia, " ".join(errores))  # segundo intento
            errores = _errores_de_estructura(eventos)
        except ValueError as error:
            errores = [str(error)]
        if errores:
            raise InterpretacionFallida(" ".join(errores))

    borradores: list[Borrador] = []
    for e in eventos:
        advertencias = []
        dia = fecha_referencia + timedelta(days=e["dia_relativo"])
        if e["hora"]:
            h, m = map(int, e["hora"].split(":"))
            momento, propuesta = datetime.combine(dia, time(h, m)), False
        else:
            momento, propuesta = None, True
        cantidad, unidad = e["cantidad"], e["unidad"]
        if cantidad is not None and unidad:
            maximo = UNIDADES_POR_TIPO[e["tipo"]][unidad]
            if not 0 < cantidad <= maximo:
                advertencias.append(f"La cantidad parece incorrecta (máximo {maximo} {unidad}). Revisala antes de confirmar.")
        borradores.append(Borrador(
            tipo=e["tipo"], descripcion=e["descripcion"].strip()[:160], cantidad=cantidad, unidad=unidad,
            fecha_hora=momento, hora_aproximada=e["hora_estimada"] or propuesta, hora_propuesta=propuesta,
            advertencias=advertencias,
        ))

    # Criterio 2: si no hay hora, el sistema propone una (la del evento anterior del mismo texto, o la del siguiente, o la hora actual / el mediodía) y la marca como propuesta.
    for i, b in enumerate(borradores):
        if b.fecha_hora is not None:
            continue
        vecinos = [x for x in borradores[:i][::-1] + borradores[i + 1:] if x.fecha_hora is not None and not x.hora_propuesta]
        if vecinos:
            b.fecha_hora = vecinos[0].fecha_hora
            origen = "la del evento mencionado junto a este"
        else:
            b.fecha_hora = datetime.combine(fecha_referencia, hora_actual or time(12, 0))
            origen = "la hora actual" if hora_actual else "el mediodía"
        b.advertencias.append(f"El texto no indica la hora: se propuso {origen}. Revisala antes de confirmar.")
    return borradores
