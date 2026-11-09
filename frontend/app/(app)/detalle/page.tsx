import { Suspense } from "react";
import DetalleDelDia from "./DetalleDelDia";

// La pantalla se muestra recién cuando el navegador confirma la sesión.
export const instant = false;

// La fecha llega en la dirección (?fecha=AAAA-MM-DD); se lee dentro de un Suspense.
export default function PaginaDetalle() {
  return (
    <Suspense fallback={<p className="text-suave">Cargando…</p>}>
      <DetalleDelDia />
    </Suspense>
  );
}
