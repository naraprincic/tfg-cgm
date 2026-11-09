"""Validación y normalización de las mediciones (HU-006), con Pandas."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.importacion.adaptadores import NOMBRES_VARIANTE, ArchivoRechazado, FilasLeidas

VALOR_MINIMO = 40    # mg/dL – intervalo admitido (HU-006, criterio 2)
VALOR_MAXIMO = 500   # mg/dL
FACTOR_MMOL = 18.016  # mmol/L -> mg/dL (diseño metodológico)
MAX_PROPORCION_INVALIDAS = 0.20  # HU-006, criterio 3

TEXTOS_BAJO = {"LOW", "LO", "BAJO"}
TEXTOS_ALTO = {"HIGH", "HI", "ALTO"}
_ZONA_EN_TEXTO = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$")


class FormatoFechaRequerido(Exception):
    """El archivo usa un formato regional de fecha: la persona tiene que confirmar cuál (día-mes o mes-día)."""

    def __init__(self, opciones: list[dict]):
        super().__init__("Confirmá el formato de fecha del archivo.")
        self.opciones = opciones


@dataclass
class ResultadoValidacion:
    formato: str
    aceptado: bool
    motivo_rechazo: str | None
    filas_glucosa: int
    filas_invalidas: int
    filas_duplicadas: int
    filas_en_conflicto: int
    mediciones_nuevas: int
    dias: int
    desde: str | None
    hasta: str | None
    detalle_invalidas: list[dict] = field(default_factory=list)
    detalle_conflictos: list[dict] = field(default_factory=list)
    formato_fecha: str | None = None  # variante confirmada o formato usado (para reproducir el proceso)
    # Mediciones listas para guardar: fecha_hora (UTC), valor, origen, marca
    nuevas: pd.DataFrame | None = None


def _clave(origen: str, momento: pd.Timestamp) -> tuple[str, int]:
    """Identifica una medición: origen + segundo exacto (independiente de la zona horaria)."""
    return origen, int(momento.timestamp())


def _interpretar_valores(leidas: FilasLeidas) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devuelve (valor en mg/dL, marca, motivo de invalidez) para cada fila."""
    texto = leidas.datos["valor_texto"].fillna("").str.strip()
    mayus = texto.str.upper()

    marca = pd.Series(None, index=texto.index, dtype=object)
    marca[mayus.isin(TEXTOS_BAJO)] = "bajo"
    marca[mayus.isin(TEXTOS_ALTO)] = "alto"

    numero = pd.to_numeric(texto.str.replace(",", ".", regex=False), errors="coerce")
    if leidas.unidad == "mmol/L":
        numero = numero * FACTOR_MMOL
    numero = numero.round()

    # «Low» / «High»: se conservan con el límite del sensor y una marca (no son inválidos).
    numero[marca == "bajo"] = VALOR_MINIMO
    numero[marca == "alto"] = leidas.limite_alto

    motivo = pd.Series(None, index=texto.index, dtype=object)
    motivo[texto == ""] = "valor de glucosa vacío"
    motivo[motivo.isna() & numero.isna()] = "valor de glucosa no numérico"
    fuera = motivo.isna() & ((numero < VALOR_MINIMO) | (numero > VALOR_MAXIMO))
    motivo[fuera] = f"valor fuera del intervalo {VALOR_MINIMO}–{VALOR_MAXIMO} mg/dL"
    return numero, marca, motivo


def _mejor_formato(texto: pd.Series, formatos: list[str]):
    """Prueba formatos SIN ambigüedad de orden día/mes entre sí (separadores, 12 o 24 horas)."""
    mejor, mejor_formato, mejor_cantidad = None, None, -1
    for formato in formatos:
        if formato == "ISO8601":
            con_zona = texto.str.contains(_ZONA_EN_TEXTO)
            if con_zona.any():
                fechas = pd.to_datetime(texto, format="ISO8601", errors="coerce", utc=True)
                fechas = fechas.where(con_zona)  # todas deben indicar zona, o ninguna
            else:
                fechas = pd.to_datetime(texto, format="ISO8601", errors="coerce")
        else:
            fechas = pd.to_datetime(texto, format=formato, errors="coerce")
        cantidad = int(fechas.notna().sum())
        if cantidad > mejor_cantidad:  # ante un empate se queda con el primero de la lista
            mejor, mejor_formato, mejor_cantidad = fechas, formato, cantidad
    return mejor, mejor_formato, mejor_cantidad


def opciones_de_formato(leidas: FilasLeidas) -> list[dict]:
    """Cómo se leería la primera fecha del archivo con cada variante regional (para que la persona elija)."""
    texto = leidas.datos["fecha_hora_texto"].fillna("").str.strip()
    no_vacias = texto[texto != ""]
    primera = no_vacias.iloc[0] if len(no_vacias) else ""
    opciones = []
    for clave, formatos in leidas.variantes_fecha.items():
        fechas, _, cantidad = _mejor_formato(no_vacias, formatos)
        lectura = fechas.iloc[0] if len(fechas) else pd.NaT
        ejemplo = (f"«{primera}» = {lectura.day} de {MESES[lectura.month - 1]} de {lectura.year}, {lectura.strftime('%H:%M')}"
                   if pd.notna(lectura) else f"«{primera}» no es una fecha válida con este formato")
        opciones.append({"id": clave, "nombre": NOMBRES_VARIANTE[clave], "ejemplo": ejemplo,
                         "filas_legibles": cantidad, "total": len(no_vacias)})
    return opciones


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _interpretar_fechas(leidas: FilasLeidas, zona: str, formato_fecha: str | None) -> tuple[pd.Series, str | None]:
    """Convierte el texto a fecha y hora en UTC (HU-006)."""
    texto = leidas.datos["fecha_hora_texto"].fillna("").str.strip()
    if leidas.variantes_fecha:
        if formato_fecha not in leidas.variantes_fecha:
            raise FormatoFechaRequerido(opciones_de_formato(leidas))
        mejor, _, _ = _mejor_formato(texto, leidas.variantes_fecha[formato_fecha])
        mejor_formato = formato_fecha
    else:
        mejor, mejor_formato, _ = _mejor_formato(texto, leidas.formatos_fecha)

    if mejor.dt.tz is None:
        # Los archivos no informan la zona: se aplica la configurada por el usuario.
        mejor = mejor.dt.tz_localize(zona, ambiguous="NaT", nonexistent="NaT")
    return mejor.dt.tz_convert("UTC"), mejor_formato


BuscarExistentes = Callable[[list[str], datetime, datetime], dict[tuple[str, int], int]]


def validar(
    leidas: FilasLeidas,
    zona_horaria: str,
    buscar_existentes: BuscarExistentes,
    formato_fecha: str | None = None,
) -> ResultadoValidacion:
    """buscar_existentes(origenes, desde, hasta) devuelve las mediciones ya guardadas del usuario en ese período como {(origen, segundo): valor}."""
    datos = leidas.datos.copy()
    if datos.empty:
        raise ArchivoRechazado("El archivo no contiene filas con mediciones de glucosa.")

    datos["valor"], datos["marca"], datos["motivo"] = _interpretar_valores(leidas)
    datos["fecha_hora"], formato_usado = _interpretar_fechas(leidas, zona_horaria, formato_fecha)
    sin_fecha = datos["fecha_hora"].isna() & datos["motivo"].isna()
    fecha_vacia = datos["fecha_hora_texto"].fillna("").str.strip() == ""
    datos.loc[sin_fecha & fecha_vacia, "motivo"] = "fecha y hora vacía"
    datos.loc[sin_fecha & ~fecha_vacia, "motivo"] = "fecha y hora ilegible"

    validas = datos[datos["motivo"].isna()].copy()
    invalidas = datos[datos["motivo"].notna()]

    # LibreView: los escaneos (prioridad 1) solo se usan si no hay un valor histórico en ese minuto.
    if (validas["prioridad"] == 1).any():
        minuto = validas["fecha_hora"].dt.floor("min")
        historicos = set(zip(validas.loc[validas["prioridad"] == 0, "origen"], minuto[validas["prioridad"] == 0]))
        tapados = (validas["prioridad"] == 1) & pd.Series(
            [(o, m) in historicos for o, m in zip(validas["origen"], minuto)], index=validas.index
        )
        validas = validas[~tapados]

    # Duplicados y conflictos dentro del archivo (HU-006, criterio 4): se conserva la primera.
    validas = validas.sort_values(["prioridad", "fila"])
    repetidas = validas.duplicated(subset=["origen", "fecha_hora"], keep="first")
    primeras = validas[~repetidas].set_index(["origen", "fecha_hora"])["valor"]
    detalle_conflictos = []
    duplicadas = conflictos = 0
    for _, fila in validas[repetidas].iterrows():
        if primeras.loc[(fila["origen"], fila["fecha_hora"])] == fila["valor"]:
            duplicadas += 1
        else:
            conflictos += 1
            detalle_conflictos.append({"fila": int(fila["fila"]), "motivo": "otro valor para la misma fecha y hora en el archivo"})
    validas = validas[~repetidas]

    # Proporción de inválidas sobre las filas de glucosa, sin contar duplicados (criterio 3).
    filas_glucosa = len(invalidas) + len(validas) + conflictos
    proporcion = len(invalidas) / filas_glucosa if filas_glucosa else 1.0
    detalle_invalidas = [
        {"fila": int(f), "motivo": m} for f, m in zip(invalidas["fila"], invalidas["motivo"])
    ][:50]

    base = dict(
        formato=leidas.formato,
        formato_fecha=formato_usado,
        filas_glucosa=filas_glucosa,
        filas_invalidas=len(invalidas),
        detalle_invalidas=detalle_invalidas,
    )
    if proporcion > MAX_PROPORCION_INVALIDAS:
        motivo = (f"El {proporcion:.0%} de las filas de glucosa son inválidas (el máximo admitido es "
                  f"{MAX_PROPORCION_INVALIDAS:.0%}). No se almacenó ninguna medición.")
        fechas_ilegibles = (invalidas["motivo"] == "fecha y hora ilegible").sum()
        if leidas.variantes_fecha and fechas_ilegibles > len(invalidas) / 2:
            motivo += " La mayoría son fechas ilegibles: probá con el otro formato de fecha."
        return ResultadoValidacion(
            **base,
            aceptado=False,
            motivo_rechazo=motivo,
            filas_duplicadas=duplicadas,
            filas_en_conflicto=conflictos,
            mediciones_nuevas=0, dias=0, desde=None, hasta=None,
            detalle_conflictos=detalle_conflictos[:50],
        )

    # Comparación con lo ya almacenado (HU-005, criterio 2): se conserva lo guardado.
    existentes = (
        buscar_existentes(
            sorted(validas["origen"].unique()),
            validas["fecha_hora"].min().to_pydatetime(),
            validas["fecha_hora"].max().to_pydatetime(),
        )
        if len(validas) else {}
    )
    nuevas_mask = []
    for origen, momento, valor, fila in zip(validas["origen"], validas["fecha_hora"], validas["valor"], validas["fila"]):
        guardado = existentes.get(_clave(origen, momento))
        if guardado is None:
            nuevas_mask.append(True)
        else:
            nuevas_mask.append(False)
            if guardado == valor:
                duplicadas += 1
            else:
                conflictos += 1
                detalle_conflictos.append({"fila": int(fila), "motivo": "ya existe otro valor almacenado para esa fecha y hora"})
    nuevas = validas[pd.Series(nuevas_mask, index=validas.index, dtype=bool)]

    locales = nuevas["fecha_hora"].dt.tz_convert(zona_horaria)
    return ResultadoValidacion(
        **base,
        aceptado=True,
        motivo_rechazo=None,
        filas_duplicadas=duplicadas,
        filas_en_conflicto=conflictos,
        mediciones_nuevas=len(nuevas),
        dias=int(locales.dt.date.nunique()),
        desde=locales.min().strftime("%d/%m/%Y %H:%M") if len(nuevas) else None,
        hasta=locales.max().strftime("%d/%m/%Y %H:%M") if len(nuevas) else None,
        detalle_conflictos=detalle_conflictos[:50],
        nuevas=nuevas[["fecha_hora", "valor", "origen", "marca"]].copy(),
    )
