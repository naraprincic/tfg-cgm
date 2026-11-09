import { Suspense } from "react";
import RegistrarEvento from "./RegistrarEvento";

// La pantalla se muestra recién cuando el navegador confirma la sesión.
export const instant = false;

export default function PaginaEventos() {
  return (
    <Suspense fallback={<p className="text-suave">Cargando…</p>}>
      <RegistrarEvento />
    </Suspense>
  );
}
