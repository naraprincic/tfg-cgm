/** Utilidades de fechas (las fechas de los días llegan como "AAAA-MM-DD"). */

export function nombreDelDia(fecha: string, conAnio = true) {
  const [a, m, d] = fecha.split("-").map(Number);
  const texto = new Date(a, m - 1, d).toLocaleDateString("es-AR", {
    weekday: "long", day: "numeric", month: "long", ...(conAnio ? { year: "numeric" } : {}),
  });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function fechaCorta(fecha: string) {
  return fecha.split("-").reverse().join("/");
}

export function sumarDias(fecha: string, dias: number) {
  const [a, m, d] = fecha.split("-").map(Number);
  const nueva = new Date(a, m - 1, d + dias);
  return `${nueva.getFullYear()}-${String(nueva.getMonth() + 1).padStart(2, "0")}-${String(nueva.getDate()).padStart(2, "0")}`;
}

export const porcentaje = (v: number) => `${v.toLocaleString("es-AR", { maximumFractionDigits: 1 })} %`;
export const numero = (v: number) => v.toLocaleString("es-AR", { maximumFractionDigits: 1 });

/** Fecha de hoy en la zona horaria del navegador, en formato AAAA-MM-DD. */
export function hoy() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
