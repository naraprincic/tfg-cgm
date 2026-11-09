"""Asociación temporal entre eventos y mediciones (HU-010)."""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

VENTANAS = {
    "comida": (-30, 180),
    "insulina": (-30, 240),
    "actividad_fisica": (0, 120),  # el 120 se cuenta desde que termina la actividad
    "sintoma": (-30, 30),
    "otro": (-30, 120),
}
AMPLIACION_HORA_APROXIMADA = 30


@dataclass
class ValorConHora:
    valor: int
    fecha_hora: datetime


@dataclass
class Asociacion:
    ventana_desde: datetime
    ventana_hasta: datetime
    mediciones_en_ventana: int
    sin_mediciones: bool
    # Comida: valor previo y máximo en las 3 h siguientes (criterio 2)
    valor_previo: ValorConHora | None = None
    maximo_posterior: ValorConHora | None = None
    # Actividad física: valor al finalizar, mínimo en las 2 h siguientes y variación (criterios 2 y 3)
    valor_al_finalizar: ValorConHora | None = None
    minimo_posterior: ValorConHora | None = None
    variacion_2h: int | None = None
    # Para todos: mínimo y máximo dentro de la ventana
    minimo_ventana: ValorConHora | None = None
    maximo_ventana: ValorConHora | None = None


def _con_hora(fila) -> ValorConHora:
    return ValorConHora(int(fila["valor"]), fila["fecha_hora"].to_pydatetime())


def asociar(
    tipo: str,
    fecha_hora: datetime,
    hora_aproximada: bool,
    duracion_min: float | None,
    mediciones: pd.DataFrame,
) -> Asociacion:
    """mediciones: columnas fecha_hora (UTC) y valor, ordenadas."""
    antes, despues = VENTANAS.get(tipo, VENTANAS["otro"])
    inicio = pd.Timestamp(fecha_hora)
    fin_evento = inicio + pd.Timedelta(minutes=duracion_min or 0) if tipo == "actividad_fisica" else inicio
    margen = AMPLIACION_HORA_APROXIMADA if hora_aproximada else 0
    desde = inicio + pd.Timedelta(minutes=antes - margen)
    hasta = fin_evento + pd.Timedelta(minutes=despues + margen)

    ventana = mediciones[(mediciones["fecha_hora"] >= desde) & (mediciones["fecha_hora"] <= hasta)]
    resultado = Asociacion(
        ventana_desde=desde.to_pydatetime(),
        ventana_hasta=hasta.to_pydatetime(),
        mediciones_en_ventana=len(ventana),
        sin_mediciones=ventana.empty,  # criterio 4: el evento se muestra igual
    )
    if ventana.empty:
        return resultado

    resultado.minimo_ventana = _con_hora(ventana.loc[ventana["valor"].idxmin()])
    resultado.maximo_ventana = _con_hora(ventana.loc[ventana["valor"].idxmax()])

    previas = ventana[ventana["fecha_hora"] <= inicio]
    if not previas.empty:
        resultado.valor_previo = _con_hora(previas.iloc[-1])

    if tipo == "comida":
        siguientes = ventana[(ventana["fecha_hora"] > inicio) & (ventana["fecha_hora"] <= inicio + pd.Timedelta(hours=3))]
        if not siguientes.empty:
            resultado.maximo_posterior = _con_hora(siguientes.loc[siguientes["valor"].idxmax()])

    if tipo == "actividad_fisica":
        hasta_fin = ventana[ventana["fecha_hora"] <= fin_evento]
        al_finalizar = hasta_fin.iloc[-1] if not hasta_fin.empty else ventana.iloc[0]
        resultado.valor_al_finalizar = _con_hora(al_finalizar)
        posteriores = ventana[(ventana["fecha_hora"] > fin_evento) & (ventana["fecha_hora"] <= fin_evento + pd.Timedelta(hours=2))]
        if not posteriores.empty:
            resultado.minimo_posterior = _con_hora(posteriores.loc[posteriores["valor"].idxmin()])
            resultado.variacion_2h = int(posteriores.iloc[-1]["valor"]) - int(al_finalizar["valor"])

    return resultado


def duracion_de_actividad(tipo: str, cantidad: float | None, unidad: str | None) -> float | None:
    """La duración de una actividad física se toma de su cantidad en minutos."""
    if tipo == "actividad_fisica" and unidad == "minutos" and cantidad:
        return float(cantidad)
    return None

