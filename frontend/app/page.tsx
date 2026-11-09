import { redirect } from "next/navigation";

// La raíz del sitio lleva a la pantalla de inicio (si no hay sesión, de ahí se pasa al login).
export default function Raiz() {
  redirect("/inicio");
}
