/** Piezas para mostrar eventos: etiqueta de tipo y texto de la asociación con las mediciones. */

import type { EventoAsociado } from "@/lib/api";
import { TIPOS, type TipoEvento } from "@/lib/eventos";

export function EtiquetaTipo({ tipo }: { tipo: string }) {
  const t = TIPOS[tipo as TipoEvento] ?? TIPOS.otro;
  return (
    <span className="rounded-md px-2 py-0.5 text-sm font-medium" style={{ background: t.fondo, color: t.texto }}>
      {t.nombre}
    </span>
  );
}

/** Relación del evento con las mediciones (HU-010). */
export function TextoAsociacion({ evento }: { evento: EventoAsociado }) {
  const a = evento.asociacion;
  if (a.sin_mediciones) {
    return <p className="text-sm text-suave">No hay mediciones disponibles entre las {a.ventana}.</p>;
  }
  const partes: string[] = [];
  if (evento.tipo === "comida") {
    if (a.valor_previo) partes.push(`antes: ${a.valor_previo.valor} mg/dL (${a.valor_previo.hora})`);
    if (a.maximo_posterior) partes.push(`máximo en las 3 h siguientes: ${a.maximo_posterior.valor} mg/dL (${a.maximo_posterior.hora})`);
    if (a.valor_previo && a.maximo_posterior) {
      const cambio = a.maximo_posterior.valor - a.valor_previo.valor;
      partes.push(`variación: ${cambio >= 0 ? "+" : ""}${cambio} mg/dL`);
    }
  } else if (evento.tipo === "actividad_fisica") {
    if (a.valor_al_finalizar) partes.push(`al finalizar: ${a.valor_al_finalizar.valor} mg/dL (${a.valor_al_finalizar.hora})`);
    if (a.minimo_posterior) partes.push(`mínimo en las 2 h siguientes: ${a.minimo_posterior.valor} mg/dL (${a.minimo_posterior.hora})`);
    if (a.variacion_2h != null) partes.push(`variación en 2 h: ${a.variacion_2h >= 0 ? "+" : ""}${a.variacion_2h} mg/dL`);
  } else {
    if (a.valor_previo) partes.push(`en ese momento: ${a.valor_previo.valor} mg/dL (${a.valor_previo.hora})`);
    if (a.minimo_ventana && a.maximo_ventana)
      partes.push(`entre ${a.minimo_ventana.valor} y ${a.maximo_ventana.valor} mg/dL en la ventana`);
  }
  return (
    <p className="text-sm text-suave">
      {partes.join(" · ") || "Mediciones disponibles en la ventana."}{" "}
      <span className="whitespace-nowrap">
        ({a.mediciones_en_ventana} mediciones, {a.ventana}
        {evento.hora_aproximada ? ", ventana ampliada por hora aproximada" : ""})
      </span>
    </p>
  );
}
