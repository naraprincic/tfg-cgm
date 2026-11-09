"""Resumen diario en lenguaje coloquial (HU-013)."""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from app.ia import cliente

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
NOMBRES_PERIODO = {
    "bajo": "por debajo de tu rango", "sobre": "por encima de tu rango",
    "bajo_nivel2": "por debajo de 54 mg/dL", "sobre_nivel2": "por encima de 250 mg/dL",
    "subida": "subida rápida", "bajada": "bajada rápida",
}
NOMBRES_TIPO = {"comida": "comida", "insulina": "insulina", "actividad_fisica": "actividad física",
                "sintoma": "síntoma", "otro": "otro"}

# Un evento se muestra junto a un momento si ocurrió durante él o en las horas previas (igual que en el semáforo).
HORAS_PREVIAS = 3
# Períodos superpuestos o separados por hasta 15 minutos se cuentan como un mismo momento del día.
SEPARACION_MOMENTOS = 15

AVISO = "Este resumen describe tus propios registros y no constituye un diagnóstico ni una indicación de tratamiento."


@dataclass
class PeriodoDatos:
    tipo: str
    desde: str
    hasta: str
    duracion_min: int
    valor_extremo: int
    valor_inicio: int | None = None
    valor_fin: int | None = None


@dataclass
class EventoDatos:
    hora: str
    tipo: str
    descripcion: str
    cantidad: float | None = None
    unidad: str | None = None


@dataclass
class DatosDia:
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
    mediciones: int
    periodos: list[PeriodoDatos] = field(default_factory=list)
    eventos: list[EventoDatos] = field(default_factory=list)


@dataclass
class ResultadoResumen:
    texto: str
    estado: str           # aprobado | plantilla
    modelo: str
    observaciones: list[str]  # motivos por los que no se aprobó el texto del modelo (si los hubo)


# Momentos del día: períodos agrupados y eventos cercanos (cálculo fijo, sin IA).

def _minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def momento_del_dia(hora: str) -> str:
    h = int(hora.split(":")[0])
    if h < 6:
        return "a la madrugada"
    if h < 12:
        return "a la mañana"
    if h < 14:
        return "al mediodía"
    if h < 20:
        return "a la tarde"
    return "a la noche"


@dataclass
class Momento:
    desde: str
    hasta: str
    periodos: list[PeriodoDatos]
    eventos_cercanos: list[tuple[EventoDatos, str]]  # (evento, "antes" | "durante")

    @property
    def cuando(self) -> str:
        return momento_del_dia(self.desde)


def agrupar_momentos(d: DatosDia) -> tuple[list[Momento], list[EventoDatos]]:
    """Agrupa los períodos que se superponen en momentos y reparte los eventos: cercanos a un momento u otros."""
    momentos: list[Momento] = []
    for p in sorted(d.periodos, key=lambda x: (x.desde, x.hasta)):
        if momentos and _minutos(p.desde) <= _minutos(momentos[-1].hasta) + SEPARACION_MOMENTOS:
            ultimo = momentos[-1]
            ultimo.periodos.append(p)
            if p.hasta > ultimo.hasta:
                ultimo.hasta = p.hasta
        else:
            momentos.append(Momento(p.desde, p.hasta, [p], []))
    otros = []
    for e in sorted(d.eventos, key=lambda x: x.hora):
        minuto = _minutos(e.hora)
        for m in momentos:  # cada evento se cuenta una sola vez, en el primer momento cercano
            inicio, fin = _minutos(m.desde), _minutos(m.hasta)
            if inicio - HORAS_PREVIAS * 60 <= minuto <= fin:
                m.eventos_cercanos.append((e, "antes" if minuto < inicio else "durante"))
                break
        else:
            otros.append(e)
    return momentos, otros


def porcentajes_redondeados(d: DatosDia) -> tuple[int, int, int]:
    """Redondea en rango, por debajo y por encima de modo que sumen lo mismo que los valores reales (sin 99 % ni 101 %)."""
    valores = [d.tir, d.tbr, d.tar]
    objetivo = round(sum(valores))
    pisos = [int(v) for v in valores]
    faltan = objetivo - sum(pisos)
    orden = sorted(range(3), key=lambda i: valores[i] - pisos[i], reverse=True)
    for i in orden[:max(faltan, 0)]:
        pisos[i] += 1
    return pisos[0], pisos[1], pisos[2]


# Datos para el modelo.

def nombre_fecha(f: date) -> str:
    return f"{DIAS[f.weekday()]} {f.day} de {MESES[f.month - 1]}"


def _n(v: float) -> str:
    """Número con coma decimal y sin decimales innecesarios (87.0 -> 87; 87.5 -> 87,5)."""
    return (f"{v:.1f}".rstrip("0").rstrip(".")).replace(".", ",")


def _describir_periodo(p: PeriodoDatos) -> str:
    if p.valor_inicio is not None:
        return (f"{p.desde} a {p.hasta}: {NOMBRES_PERIODO[p.tipo]}, de {p.valor_inicio} a {p.valor_fin} mg/dL "
                f"({abs(p.valor_fin - p.valor_inicio)} mg/dL en {p.duracion_min} minutos)")
    extremo = "mínimo" if p.tipo.startswith("bajo") else "máximo"
    return f"{p.desde} a {p.hasta}: {NOMBRES_PERIODO[p.tipo]}, {extremo} {p.valor_extremo} mg/dL ({p.duracion_min} minutos)"


def _describir_evento(e: EventoDatos) -> str:
    cantidad = f" ({_n(e.cantidad)} {e.unidad})" if e.cantidad is not None and e.unidad else ""
    return f"{e.hora}: {NOMBRES_TIPO.get(e.tipo, e.tipo)}, {e.descripcion}{cantidad}"


def datos_como_texto(d: DatosDia) -> str:
    en_rango, abajo, arriba = porcentajes_redondeados(d)
    lineas = [
        f"Fecha: {nombre_fecha(d.fecha)} ({d.fecha.strftime('%d/%m/%Y')}).",
        f"Rango objetivo personal: {d.rango_min} a {d.rango_max} mg/dL.",
        f"Tiempo en rango de 70 a 180 mg/dL (consenso): {_n(d.tir)} %. Por debajo de 70: {_n(d.tbr)} % "
        f"(por debajo de 54: {_n(d.tbr_nivel2)} %). Por encima de 180: {_n(d.tar)} % (por encima de 250: {_n(d.tar_nivel2)} %).",
        f"Redondeados para el texto (suman lo mismo que los reales): en rango {en_rango} %, por debajo {abajo} %, por encima {arriba} %.",
    ]
    if (d.rango_min, d.rango_max) != (70, 180):
        lineas.append(f"Tiempo dentro del rango personal ({d.rango_min} a {d.rango_max}): {_n(d.tir_personal)} %. "
                      "Los momentos de abajo usan el rango personal.")
    lineas += [
        f"Glucosa promedio: {_n(d.glucosa_promedio)} mg/dL. Coeficiente de variación: {_n(d.coeficiente_variacion)} %.",
        f"Cobertura del día: {_n(d.cobertura)} %{' (datos parciales: menos del 70 %)' if d.parcial else ''}. Mediciones: {d.mediciones}.",
    ]
    momentos, otros = agrupar_momentos(d)
    if momentos:
        lineas.append(f"Momentos relevantes del día (cada uno agrupa períodos que se superponen; eventos cercanos = "
                      f"registrados durante el momento o en las {HORAS_PREVIAS} horas previas):")
        for n, m in enumerate(momentos, 1):
            horas = sorted({p.desde for p in m.periodos})
            lineas.append(f"Momento {n}, {m.cuando}, de {m.desde} a {m.hasta} "
                          f"(horas de inicio que el texto tiene que nombrar: {', '.join(horas)}):")
            lineas += [f"  - {_describir_periodo(p)}" for p in m.periodos]
            if m.eventos_cercanos:
                for e, relacion in m.eventos_cercanos:
                    cuando = (f"{_cercania(e, m)} del inicio" if relacion == "antes" else "durante el momento")
                    lineas.append(f"  - evento cercano ({cuando}): {_describir_evento(e)}")
            else:
                lineas.append("  - sin eventos registrados cerca")
    else:
        lineas.append("Momentos relevantes: ninguno (no hubo períodos fuera del rango personal ni cambios rápidos).")
    if otros:
        lineas.append("Otros eventos registrados, lejos de los momentos relevantes:")
        lineas += [f"- {_describir_evento(e)}" for e in otros]
    elif not d.eventos:
        lineas.append("Eventos registrados: ninguno.")
    return "\n".join(lineas)


INSTRUCCIONES = """Redactás el resumen diario de una aplicación que organiza los datos de glucosa de una persona con diabetes.
Escribí en español rioplatense (voseo), con un tono cercano y claro, para alguien sin formación técnica ni clínica.

Cómo armar el texto (un solo párrafo, entre 4 y 7 oraciones, sin viñetas ni títulos):
1. Una o dos oraciones con el panorama del día: tiempo en rango, cuánto estuvo por debajo y por encima (usá los
   porcentajes redondeados que te doy), el promedio y la variabilidad. Nombrá cada indicador una sola vez.
2. Contá los momentos relevantes en orden de hora, uno por oración. Si un momento agrupa varios tramos (por ejemplo,
   una subida rápida y un tramo por encima del rango), contalos juntos como una sola situación, pero nombrá la hora de
   inicio de CADA tramo, por ejemplo: "A la tarde, desde las 16:20 subió rápido de 137 a 227 mg/dL y a partir de las
   16:50 quedó por encima de tu rango hasta las 18:50". No repitas en cada oración la misma fórmula: variá los verbos
   (subió, se mantuvo, bajó, quedó).
3. Si un momento tiene eventos cercanos, mencionalos en esa misma oración como algo que ocurrió antes o durante
   ("unos minutos antes habías registrado una caminata", "en ese horario anotaste el almuerzo"). Los eventos lejanos
   pueden ir juntos en una oración breve al final, sin detalle.
4. Si mencionaste eventos cercanos, cerrá con una oración breve que aclare que una coincidencia en el horario no muestra
   por sí sola qué produjo el cambio.
5. Si ningún momento tiene eventos cercanos, decilo en una oración simple ("No registraste eventos cerca de estos
   momentos."), sin especular sobre qué podría haber influido.
6. Si los datos son parciales, decilo en una oración.
7. Nombrá el día por su fecha (por ejemplo, "El sábado 7 de noviembre"); no digas "hoy" ni "ayer".

Reglas obligatorias:
- Usá SOLO los datos que te doy. Cada número tiene que aparecer en los datos (los porcentajes, como enteros).
- Mencioná el tiempo en rango, el promedio, la variabilidad y la hora de inicio (HH:MM) de CADA período listado.
- Nunca afirmes que un evento causó o explica un cambio: solo que ocurrió antes, durante o después.
- Prohibido: diagnósticos, valoraciones ("bien", "mal", "buen control", "normal", "preocupante"), causas ("porque",
  "debido a", "provocó", "por la comida"), recomendaciones o indicaciones ("deberías", "te recomiendo", "conviene",
  "ajustá", "consultá") y dosis.
- No uses la palabra "período": hablá de momentos, horarios o tramos."""

ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["resumen"],
    "properties": {"resumen": {"type": "string"}},
}


# Verificación automática (criterio 2)

_SIN_TILDES = str.maketrans("áéíóúü", "aeiouu")

FRASES_PROHIBIDAS = [
    # causas
    r"\bporque\b", r"\bdebido a\b", r"\ba causa de\b", r"\bse debe\b", r"\bse debio\b", r"\bprovoc", r"\bcaus[oó]\b",
    r"\bcausad", r"\bpor culpa\b", r"\bhizo que\b", r"\bgenero (una|un|la|el)\b", r"\bproducto de\b", r"\bresultado de\b",
    # diagnósticos y valoraciones
    r"\bdiagnost", r"\bbuen control\b", r"\bmal control\b", r"\bdescompens", r"\bpreocupante\b", r"\bgrave\b", r"\bpeligros",
    # recomendaciones e indicaciones
    r"\bdeberias\b", r"\bdebes\b", r"\btenes que\b", r"\bte recomiendo\b", r"\brecomend", r"\bsugiero\b", r"\bte sugiero\b",
    r"\bconviene\b", r"\bseria bueno\b", r"\bseria conveniente\b", r"\bajusta (la|tu|el|los|las)\b",
    r"\bconsulta (a|con) (tu|un|una|el|la)\b", r"\bconsultes\b", r"\bdosis\b", r"\btratamiento\b",
    r"\bintenta\b", r"\bprocura\b", r"\bes importante que\b",
    # más causas y valoraciones
    r"\ba raiz de\b", r"\bconsecuencia\b", r"\bpor efecto\b", r"\bel efecto de\b", r"\binfluy", r"\bexplica (el|la|los|las)\b",
    r"\bpor (la|el) (comida|almuerzo|cena|desayuno|merienda|insulina|caminata|actividad|ejercicio)\b",
    r"\b(subio|bajo|aumento|descendio|cayo|fue|se dio|ocurrio) por (?!debajo|encima)", r"\bpor (haber|comer|cenar|almorzar|desayunar|merendar)\b",
    r"\binflu(ir|yo|ye|yen|yeron|encia|encio)\b", r"\bque (pudo|podria|puede) (haber )?(causado|provocado|generado|influido)",
    r"\b(hoy|ayer)\b",
    r"\bnormal(es)?\b", r"\bexcelente\b", r"\bmuy bien\b", r"\bbien controlad", r"\balarmante\b", r"\briesgo\b",
]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto.lower()).translate(_SIN_TILDES)
    return texto


def numeros_permitidos(d: DatosDia) -> set[str]:
    """Todos los números que el texto puede contener (con sus redondeos)."""
    valores: set[float] = {54, 70, 180, 250, d.rango_min, d.rango_max, d.mediciones, 24, 100,
                           d.fecha.day, d.fecha.month, d.fecha.year, d.fecha.year % 100}
    for v in (d.tir, d.tir_personal, d.tbr, d.tbr_nivel2, d.tar, d.tar_nivel2,
              d.glucosa_promedio, d.coeficiente_variacion, d.cobertura):
        valores |= {round(v, 1), round(v), math.floor(v), math.ceil(v)}
    for p in d.periodos:
        valores |= {p.duracion_min, p.valor_extremo}
        valores |= {x for x in (p.valor_inicio, p.valor_fin) if x is not None}
        if p.valor_inicio is not None and p.valor_fin is not None:
            valores.add(abs(p.valor_fin - p.valor_inicio))
        horas = round(p.duracion_min / 60, 1)
        valores |= {horas, round(horas)} if p.duracion_min >= 60 else set()
    for e in d.eventos:
        if e.cantidad is not None:
            valores.add(e.cantidad)
    valores |= set(porcentajes_redondeados(d))
    # Cantidades chicas escritas con números (por ejemplo "2 períodos").
    valores |= set(range(0, 11))
    permitidos = {_n(float(v)) for v in valores}
    # Horas que pueden aparecer.
    horas = {p.desde for p in d.periodos} | {p.hasta for p in d.periodos} | {e.hora for e in d.eventos}
    return permitidos | horas


_NUMERO = re.compile(r"\b\d{1,2}:\d{2}\b|\d+(?:[.,]\d+)?")


def verificar(texto: str, d: DatosDia) -> list[str]:
    """Verificación automática del texto del modelo."""
    problemas = []
    if not texto or len(texto.strip()) < 40:
        problemas.append("El texto está vacío o es demasiado corto.")
        return problemas

    permitidos = numeros_permitidos(d)
    for encontrado in _NUMERO.findall(texto):
        normal = encontrado if ":" in encontrado else _n(float(encontrado.replace(",", ".")))
        if normal not in permitidos:
            problemas.append(f"Incluye un número que no coincide con los datos calculados: {encontrado}.")

    # Omisiones: los indicadores principales y todos los períodos relevantes deben estar.
    numeros = {e if ":" in e else _n(float(e.replace(",", "."))) for e in _NUMERO.findall(texto)}
    for nombre, valor in (("el tiempo en rango", d.tir), ("la glucosa promedio", d.glucosa_promedio),
                          ("la variabilidad (coeficiente de variación)", d.coeficiente_variacion)):
        redondeos = {round(valor, 1), round(valor), math.floor(valor), math.ceil(valor)}
        if not {_n(float(v)) for v in redondeos} & numeros:
            problemas.append(f"Omite {nombre} ({_n(round(valor, 1))}).")
    for p in d.periodos:
        if p.desde not in texto:
            problemas.append(f"Omite el período relevante que empieza a las {p.desde}.")

    normal = _normalizar(texto)
    for patron in FRASES_PROHIBIDAS:
        coincidencia = re.search(patron, normal)
        if coincidencia:
            problemas.append(f"Incluye una expresión no permitida (causa, diagnóstico o indicación): «{coincidencia.group(0)}».")
    return problemas


# Plantilla automática (sin inteligencia artificial)

def _lista(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def _frase_periodo(p: PeriodoDatos, primero: bool) -> str:
    sujeto = "tu glucosa " if primero else ""
    if p.tipo == "subida":
        return f"{sujeto}subió rápido de {p.valor_inicio} a {p.valor_fin} mg/dL entre las {p.desde} y las {p.hasta}"
    if p.tipo == "bajada":
        return f"{sujeto}bajó rápido de {p.valor_inicio} a {p.valor_fin} mg/dL entre las {p.desde} y las {p.hasta}"
    if p.tipo == "sobre":
        return f"{sujeto}estuvo por encima de tu rango de {p.desde} a {p.hasta}, con un máximo de {p.valor_extremo} mg/dL"
    if p.tipo == "bajo":
        return f"{sujeto}estuvo por debajo de tu rango de {p.desde} a {p.hasta}, con un mínimo de {p.valor_extremo} mg/dL"
    if p.tipo == "sobre_nivel2":
        return f"{sujeto}pasó de 250 mg/dL de {p.desde} a {p.hasta}"
    return f"{sujeto}quedó por debajo de 54 mg/dL de {p.desde} a {p.hasta}"


def _nombre_evento(e: EventoDatos, con_hora: bool = True) -> str:
    descripcion = e.descripcion.strip()
    descripcion = descripcion[:1].lower() + descripcion[1:]
    tipo = NOMBRES_TIPO.get(e.tipo, e.tipo)
    # "almuerzo: ensalada" ya dice que es una comida; "insulina rápida" ya dice que es insulina.
    nombre = descripcion if (e.tipo == "comida" or tipo in descripcion.lower()) and descripcion else f"{tipo}: {descripcion}"
    if e.cantidad is not None and e.unidad:
        nombre += f" ({_n(e.cantidad)} {e.unidad})"
    return f"{nombre} a las {e.hora}" if con_hora else nombre


def _cercania(e: EventoDatos, m: "Momento") -> str:
    minutos_antes = _minutos(m.desde) - _minutos(e.hora)
    return "poco antes" if minutos_antes <= 60 else "en las horas previas"


def plantilla(d: DatosDia) -> str:
    """Resumen armado con reglas fijas, a partir de los mismos datos (respaldo cuando la IA no está o falla)."""
    en_rango, abajo, arriba = porcentajes_redondeados(d)
    partes = [f"El {nombre_fecha(d.fecha)} tu glucosa estuvo entre 70 y 180 mg/dL el {en_rango} % del tiempo"]
    if abajo or arriba:
        detalle = [x for x in (f"el {abajo} % por debajo" if abajo else "", f"el {arriba} % por encima" if arriba else "") if x]
        partes[0] += "; " + " y ".join(detalle)
    partes[0] += "."
    if (d.rango_min, d.rango_max) != (70, 180):
        partes.append(f"Dentro de tu rango personal, de {d.rango_min} a {d.rango_max} mg/dL, estuvo el {round(d.tir_personal)} % del tiempo.")
    partes.append(f"El promedio fue de {round(d.glucosa_promedio)} mg/dL y la variabilidad, del {round(d.coeficiente_variacion)} %.")

    momentos, otros = agrupar_momentos(d)
    hubo_coincidencias = False
    otra_vez = ["Más tarde", "Un rato después", "Después"]
    anterior = None
    for n, m in enumerate(momentos):
        frases = [_frase_periodo(p, n == 0 and i == 0) for i, p in enumerate(m.periodos)]
        apertura = otra_vez[n % len(otra_vez)] if m.cuando == anterior else m.cuando[0].upper() + m.cuando[1:]
        anterior = m.cuando
        oracion = f"{apertura}, {_lista(frases)}."
        if m.eventos_cercanos:
            hubo_coincidencias = True
            trozos = []
            for cercania in ("poco antes", "en las horas previas"):
                lista = [_nombre_evento(e) for e, r in m.eventos_cercanos if r == "antes" and _cercania(e, m) == cercania]
                if lista:
                    trozos.append(f"{cercania} habías registrado {_lista(lista)}")
            durante = [_nombre_evento(e) for e, r in m.eventos_cercanos if r == "durante"]
            if durante:
                trozos.append(f"en ese horario registraste {_lista(durante)}")
            texto = "; ".join(trozos)
            oracion += f" {texto[0].upper()}{texto[1:]}."
        partes.append(oracion)
    if not momentos:
        partes.append("No hubo momentos fuera de tu rango ni cambios rápidos.")
    if otros:
        nombres = [_nombre_evento(e) for e in otros]
        partes.append(f"{'También registraste' if hubo_coincidencias else 'Registraste'} {_lista(nombres)}.")
    if hubo_coincidencias:
        partes.append("Que un evento coincida en el horario no muestra por sí solo qué produjo el cambio.")
    if d.parcial:
        partes.append(f"Ese día el sensor registró datos del {round(d.cobertura)} % del tiempo, así que estos valores "
                      "describen solo una parte del día.")
    return " ".join(partes)


# Generación.

def generar(d: DatosDia) -> ResultadoResumen:
    """Pide el resumen al modelo, lo verifica y, si no se aprueba, usa la plantilla."""
    observaciones: list[str] = []
    if cliente.disponible():
        datos = datos_como_texto(d)
        correccion = None
        for _ in range(2):  # un intento y, si falla la verificación, uno más (criterio 2)
            pedido = datos if not correccion else f"{datos}\n\nTu texto anterior tenía estos problemas, corregilos:\n{correccion}"
            try:
                texto = cliente.llamar_json(INSTRUCCIONES, pedido, "resumen_diario", ESQUEMA)["resumen"].strip()
            except cliente.ServicioNoDisponible as error:
                observaciones.append(str(error))
                break
            except (ValueError, KeyError):
                observaciones.append("La respuesta del modelo no tuvo el formato esperado.")
                correccion = "La respuesta debe ser un JSON con el campo resumen."
                continue
            problemas = verificar(texto, d)
            if not problemas:
                return ResultadoResumen(texto=texto, estado="aprobado", modelo=cliente.modelo(), observaciones=observaciones)
            observaciones.extend(p for p in problemas if p not in observaciones)
            correccion = "\n".join(f"- {p}" for p in problemas)
    else:
        observaciones.append("La inteligencia artificial no está configurada.")
    return ResultadoResumen(texto=plantilla(d), estado="plantilla", modelo="plantilla automática", observaciones=observaciones)
