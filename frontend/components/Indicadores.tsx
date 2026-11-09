/** Tarjetas de indicadores del día (Figuras 6 y 9 de la tesis). */

import type { Indicadores } from "@/lib/api";
import { numero, porcentaje } from "@/lib/fechas";

export function Tarjeta({ titulo, valor, detalle, destacado }: { titulo: string; valor: string; detalle?: string; destacado?: boolean }) {
  return (
    <div className="rounded-xl border border-borde bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-suave">{titulo}</p>
      <p className={`font-bold text-marca ${destacado ? "text-3xl" : "text-2xl"}`}>{valor}</p>
      {detalle && <p className="text-xs text-suave">{detalle}</p>}
    </div>
  );
}

/** Los cuatro indicadores principales (pantalla de inicio). */
export function IndicadoresPrincipales({ i }: { i: Indicadores }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tarjeta destacado titulo="Tiempo en rango" valor={porcentaje(i.tir)} detalle="70–180 mg/dL (consenso)" />
      <Tarjeta destacado titulo="Tiempo bajo rango" valor={porcentaje(i.tbr)} detalle={`<54 mg/dL: ${porcentaje(i.tbr_nivel2)}`} />
      <Tarjeta destacado titulo="Tiempo sobre rango" valor={porcentaje(i.tar)} detalle={`>250 mg/dL: ${porcentaje(i.tar_nivel2)}`} />
      <Tarjeta destacado titulo="Promedio" valor={numero(Math.round(i.glucosa_promedio))} detalle="mg/dL" />
    </div>
  );
}

/** Todos los indicadores del día (detalle del día). */
export function IndicadoresCompletos({ i }: { i: Indicadores }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tarjeta titulo="Tiempo en rango" valor={porcentaje(i.tir)} detalle="70–180 mg/dL (consenso)" />
      <Tarjeta titulo="En tu rango personal" valor={porcentaje(i.tir_personal)} detalle={`${i.rango_min}–${i.rango_max} mg/dL`} />
      <Tarjeta titulo="Bajo rango" valor={porcentaje(i.tbr)} detalle={`<70 · <54: ${porcentaje(i.tbr_nivel2)}`} />
      <Tarjeta titulo="Sobre rango" valor={porcentaje(i.tar)} detalle={`>180 · >250: ${porcentaje(i.tar_nivel2)}`} />
      <Tarjeta titulo="Glucosa promedio" valor={numero(i.glucosa_promedio)} detalle="mg/dL, ponderada por tiempo" />
      <Tarjeta titulo="Coef. de variación" valor={porcentaje(i.coeficiente_variacion)} detalle="desvío ÷ promedio" />
      <Tarjeta titulo="Cobertura" valor={porcentaje(i.cobertura)} detalle={i.parcial ? "Parcial: menos del 70 %" : "minutos con datos"} />
      <Tarjeta titulo="Mediciones" valor={numero(i.mediciones_validas)} detalle="usadas en el cálculo" />
    </div>
  );
}
