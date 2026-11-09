"""Adaptadores de formato (Anexo I de la tesis)."""

import csv
import io
import unicodedata
from dataclasses import dataclass, field

import pandas as pd


class ArchivoRechazado(Exception):
    """El archivo completo no puede procesarse; el mensaje explica el motivo (HU-006, criterio 1)."""


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios extra, para comparar nombres de columnas."""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().strip().split())


@dataclass
class FilasLeidas:
    """Resultado de un adaptador: las filas de glucosa en la estructura común."""

    formato: str
    datos: pd.DataFrame  # columnas: fila, fecha_hora_texto, valor_texto, origen, prioridad
    formatos_fecha: list[str]  # formatos de fecha y hora sin ambigüedad (año primero), a probar en orden
    unidad: str  # "mg/dL" o "mmol/L"
    limite_alto: int  # valor que se registra para «High» (límite superior del sensor)
    filas_ignoradas: int = 0  # alertas, datos de paciente, otros tipos de registro
    avisos: list[str] = field(default_factory=list)
    # Formatos regionales (día y mes en distinto orden): la persona confirma cuál usa el archivo.
    variantes_fecha: dict[str, list[str]] | None = None


# Variantes regionales de fecha de LibreView.
VARIANTES_REGIONALES = {
    "mes-dia": ["%m-%d-%Y %H:%M", "%m/%d/%Y %H:%M", "%m-%d-%Y %I:%M %p", "%m/%d/%Y %I:%M %p", "%Y-%m-%d %H:%M"],
    "dia-mes": ["%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y %I:%M %p", "%d/%m/%Y %I:%M %p", "%Y-%m-%d %H:%M"],
}
NOMBRES_VARIANTE = {"mes-dia": "Mes, día y año (MM-DD-AAAA)", "dia-mes": "Día, mes y año (DD-MM-AAAA)"}


def _buscar_columna(columnas: list[str], variantes: list[str]) -> str | None:
    """Devuelve la columna real cuyo nombre normalizado coincide con alguna variante."""
    normalizadas = {_normalizar(c): c for c in columnas}
    for variante in variantes:
        if _normalizar(variante) in normalizadas:
            return normalizadas[_normalizar(variante)]
    return None


def _leer_tabla(texto: str, fila_cabecera: int, separador: str) -> pd.DataFrame:
    """Lee el CSV a partir de la cabecera, todo como texto (la validación viene después)."""
    tabla = pd.read_csv(
        io.StringIO(texto),
        sep=separador,
        skiprows=fila_cabecera,
        dtype=str,
        keep_default_na=False,
        skip_blank_lines=False,
        on_bad_lines="skip",
        engine="python",
    )
    tabla.columns = [str(c).strip() for c in tabla.columns]
    # Número de fila tal como lo ve la persona en el archivo (1 = primera línea).
    tabla["fila"] = range(fila_cabecera + 2, fila_cabecera + 2 + len(tabla))
    return tabla


# LibreView (Abbott)

LIBRE_FECHA = ["Device Timestamp", "Sello de tiempo del dispositivo", "Marca de tiempo del dispositivo"]
LIBRE_TIPO = ["Record Type", "Tipo de registro"]
LIBRE_HIST_MG = ["Historic Glucose mg/dL", "Historial de glucosa mg/dL"]
LIBRE_HIST_MMOL = ["Historic Glucose mmol/L", "Historial de glucosa mmol/L"]
LIBRE_SCAN_MG = ["Scan Glucose mg/dL", "Escaneo de glucosa mg/dL"]
LIBRE_SCAN_MMOL = ["Scan Glucose mmol/L", "Escaneo de glucosa mmol/L"]
LIBRE_DISPOSITIVO = ["Device", "Dispositivo"]
LIBRE_SERIE = ["Serial Number", "Número de serie"]


def es_libreview(cabecera: list[str]) -> bool:
    return bool(_buscar_columna(cabecera, LIBRE_FECHA) and _buscar_columna(cabecera, LIBRE_TIPO))


def leer_libreview(texto: str, fila_cabecera: int) -> FilasLeidas:
    tabla = _leer_tabla(texto, fila_cabecera, ",")
    cols = list(tabla.columns)
    col_fecha = _buscar_columna(cols, LIBRE_FECHA)
    col_tipo = _buscar_columna(cols, LIBRE_TIPO)

    hist_mg, hist_mmol = _buscar_columna(cols, LIBRE_HIST_MG), _buscar_columna(cols, LIBRE_HIST_MMOL)
    scan_mg, scan_mmol = _buscar_columna(cols, LIBRE_SCAN_MG), _buscar_columna(cols, LIBRE_SCAN_MMOL)
    if hist_mg or scan_mg:
        unidad, col_hist, col_scan = "mg/dL", hist_mg, scan_mg
    elif hist_mmol or scan_mmol:
        unidad, col_hist, col_scan = "mmol/L", hist_mmol, scan_mmol
    else:
        raise ArchivoRechazado(
            "El archivo de LibreView no tiene la columna de glucosa "
            "(«Historic Glucose mg/dL» o «Historic Glucose mmol/L»)."
        )

    col_disp = _buscar_columna(cols, LIBRE_DISPOSITIVO)
    col_serie = _buscar_columna(cols, LIBRE_SERIE)
    col_id = col_serie or col_disp
    identificador = tabla[col_id] if col_id else pd.Series("", index=tabla.index)
    origen = ("LibreView " + identificador).str.strip().str.slice(0, 40)

    tipo = tabla[col_tipo].str.strip()
    filas = []
    # Tipo 0: historial automático (prioridad 0).
    if col_hist:
        h = tabla[tipo == "0"]
        filas.append(pd.DataFrame({
            "fila": h["fila"], "fecha_hora_texto": h[col_fecha], "valor_texto": h[col_hist],
            "origen": origen[h.index], "prioridad": 0,
        }))
    if col_scan:
        s = tabla[tipo == "1"]
        filas.append(pd.DataFrame({
            "fila": s["fila"], "fecha_hora_texto": s[col_fecha], "valor_texto": s[col_scan],
            "origen": origen[s.index], "prioridad": 1,
        }))
    datos = pd.concat(filas, ignore_index=True) if filas else pd.DataFrame()
    ignoradas = len(tabla) - len(datos)

    return FilasLeidas(
        formato="LibreView",
        datos=datos,
        # El orden de día y mes depende de la configuración regional de quien exportó: se pide confirmación (ver VARIANTES_REGIONALES).
        formatos_fecha=[],
        variantes_fecha=VARIANTES_REGIONALES,
        unidad=unidad,
        limite_alto=500,
        filas_ignoradas=ignoradas,
    )


# Dexcom Clarity.

DEX_FECHA = ["Timestamp (YYYY-MM-DDThh:mm:ss)", "Marca temporal (AAAA-MM-DDThh:mm:ss)"]
DEX_EVENTO = ["Event Type", "Tipo de evento"]
DEX_GLUC_MG = ["Glucose Value (mg/dL)", "Valor de glucosa (mg/dL)", "Nivel de glucosa (mg/dL)"]
DEX_GLUC_MMOL = ["Glucose Value (mmol/L)", "Valor de glucosa (mmol/L)", "Nivel de glucosa (mmol/L)"]
DEX_DISPOSITIVO = ["Source Device ID", "ID del dispositivo de origen"]


def es_dexcom(cabecera: list[str]) -> bool:
    return bool(_buscar_columna(cabecera, DEX_FECHA) and _buscar_columna(cabecera, DEX_EVENTO))


def leer_dexcom(texto: str, fila_cabecera: int) -> FilasLeidas:
    tabla = _leer_tabla(texto, fila_cabecera, ",")
    cols = list(tabla.columns)
    col_fecha = _buscar_columna(cols, DEX_FECHA)
    col_evento = _buscar_columna(cols, DEX_EVENTO)
    col_mg, col_mmol = _buscar_columna(cols, DEX_GLUC_MG), _buscar_columna(cols, DEX_GLUC_MMOL)
    if not (col_mg or col_mmol):
        raise ArchivoRechazado(
            "El archivo de Dexcom Clarity no tiene la columna de glucosa («Glucose Value (mg/dL)»)."
        )
    col_valor, unidad = (col_mg, "mg/dL") if col_mg else (col_mmol, "mmol/L")
    col_disp = _buscar_columna(cols, DEX_DISPOSITIVO)

    # Solo las lecturas del sensor (Event Type = EGV); paciente, dispositivo y alertas se ignoran.
    egv = tabla[tabla[col_evento].str.strip().str.upper() == "EGV"]
    identificador = egv[col_disp] if col_disp else pd.Series("", index=egv.index)
    origen = ("Dexcom " + identificador).str.strip().str.slice(0, 40)
    datos = pd.DataFrame({
        "fila": egv["fila"], "fecha_hora_texto": egv[col_fecha], "valor_texto": egv[col_valor],
        "origen": origen, "prioridad": 0,
    })
    return FilasLeidas(
        formato="Dexcom Clarity",
        datos=datos.reset_index(drop=True),
        formatos_fecha=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
        unidad=unidad,
        limite_alto=400,
        filas_ignoradas=len(tabla) - len(egv),
    )


# Genérico.

GEN_FECHA = ["fecha_hora"]
GEN_GLUCOSA = ["glucosa_mg_dl"]
GEN_ORIGEN = ["origen"]


def es_generico(cabecera: list[str]) -> bool:
    return bool(_buscar_columna(cabecera, GEN_FECHA) or _buscar_columna(cabecera, GEN_GLUCOSA))


def leer_generico(texto: str, fila_cabecera: int, separador: str) -> FilasLeidas:
    tabla = _leer_tabla(texto, fila_cabecera, separador)
    cols = list(tabla.columns)
    col_fecha, col_gluc = _buscar_columna(cols, GEN_FECHA), _buscar_columna(cols, GEN_GLUCOSA)
    faltan = [n for n, c in (("fecha_hora", col_fecha), ("glucosa_mg_dl", col_gluc)) if not c]
    if faltan:
        raise ArchivoRechazado(
            "Al archivo le faltan las columnas obligatorias: " + ", ".join(faltan) + "."
        )
    col_origen = _buscar_columna(cols, GEN_ORIGEN)
    origen = tabla[col_origen].str.strip().str.slice(0, 40) if col_origen else "Archivo genérico"
    datos = pd.DataFrame({
        "fila": tabla["fila"], "fecha_hora_texto": tabla[col_fecha], "valor_texto": tabla[col_gluc],
        "origen": origen, "prioridad": 0,
    })
    # Se descartan las líneas totalmente vacías (por ejemplo, al final del archivo).
    datos = datos[(datos["fecha_hora_texto"].str.strip() != "") | (datos["valor_texto"].str.strip() != "")]
    return FilasLeidas(
        formato="Genérico",
        datos=datos.reset_index(drop=True),
        formatos_fecha=[
            "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S",
            "ISO8601",  # admite también la zona horaria escrita en el texto (+00:00, Z)
        ],
        unidad="mg/dL",
        limite_alto=500,
    )


# Detección del formato.

def _decodificar(contenido: bytes) -> str:
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ArchivoRechazado("No se pudo leer el texto del archivo.")


def leer_archivo(nombre_archivo: str, contenido: bytes) -> FilasLeidas:
    """Reconoce el formato del archivo y lo traduce a la estructura común."""
    if not nombre_archivo.lower().endswith(".csv"):
        raise ArchivoRechazado("El archivo debe tener extensión .csv.")
    if not contenido.strip():
        raise ArchivoRechazado("El archivo está vacío.")

    texto = _decodificar(contenido)
    lineas = texto.splitlines()

    # Se buscan las primeras líneas hasta encontrar una cabecera conocida (LibreView y Dexcom tienen filas previas que se omiten).
    for indice, linea in enumerate(lineas[:30]):
        for separador in (",", ";"):
            cabecera = next(csv.reader([linea], delimiter=separador), [])
            if len(cabecera) < 2:
                continue
            if separador == "," and es_libreview(cabecera):
                return leer_libreview(texto, indice)
            if separador == "," and es_dexcom(cabecera):
                return leer_dexcom(texto, indice)
            if es_generico(cabecera):
                return leer_generico(texto, indice, separador)

    raise ArchivoRechazado(
        "El archivo no coincide con ningún formato admitido (LibreView, Dexcom Clarity o genérico "
        "con las columnas fecha_hora y glucosa_mg_dl)."
    )
