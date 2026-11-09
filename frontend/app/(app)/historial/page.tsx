import PantallaHistorial from "./PantallaHistorial";

// La pantalla se muestra recién cuando el navegador confirma la sesión: no se valida para navegación instantánea (evita un aviso de Next.js en modo desarrollo).
export const instant = false;

export default function Pagina() {
  return <PantallaHistorial />;
}
