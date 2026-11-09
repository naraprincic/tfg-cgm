/** Nombres, colores y unidades de los tipos de evento (Figuras 6, 8 y 9 de la tesis). */

export type TipoEvento = "comida" | "insulina" | "actividad_fisica" | "sintoma" | "otro";

export const TIPOS: Record<TipoEvento, { nombre: string; fondo: string; texto: string; color: string; unidades: string[] }> = {
  comida: { nombre: "Comida", fondo: "#fde4e1", texto: "#b3261e", color: "#d9534f", unidades: ["porciones", "gramos"] },
  insulina: { nombre: "Insulina", fondo: "#e1ecfb", texto: "#1f5fa8", color: "#2f6fb6", unidades: ["unidades"] },
  actividad_fisica: { nombre: "Actividad física", fondo: "#e3f1e1", texto: "#2e7d32", color: "#43a047", unidades: ["minutos"] },
  sintoma: { nombre: "Síntoma", fondo: "#fbe3f1", texto: "#9c2a6e", color: "#b0397f", unidades: [] },
  otro: { nombre: "Otro", fondo: "#eceff1", texto: "#455a64", color: "#607d8b", unidades: ["minutos"] },
};

export function nombreTipo(tipo: string) {
  return TIPOS[tipo as TipoEvento]?.nombre ?? tipo;
}

export function cantidadTexto(cantidad: number | null, unidad: string | null) {
  if (cantidad == null || !unidad) return "";
  const n = Number.isInteger(cantidad) ? cantidad : cantidad.toFixed(1);
  const singular: Record<string, string> = { porciones: "porción", gramos: "gramo", unidades: "unidad", minutos: "minuto" };
  return `${n} ${cantidad === 1 ? singular[unidad] ?? unidad : unidad}`;
}

export const PERIODOS: Record<string, { nombre: string; color: string }> = {
  bajo: { nombre: "Bajo el rango", color: "rgba(217, 83, 79, 0.10)" },
  bajo_nivel2: { nombre: "Bajo 54 mg/dL (nivel 2)", color: "rgba(217, 83, 79, 0.18)" },
  sobre: { nombre: "Sobre el rango", color: "rgba(245, 166, 35, 0.12)" },
  sobre_nivel2: { nombre: "Sobre 250 mg/dL (nivel 2)", color: "rgba(245, 166, 35, 0.22)" },
  subida: { nombre: "Subida rápida", color: "rgba(47, 111, 182, 0.08)" },
  bajada: { nombre: "Bajada rápida", color: "rgba(47, 111, 182, 0.08)" },
};
