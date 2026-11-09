/** Mensajes que deben mostrarse en la pantalla siguiente (por ejemplo, "tu sesión se cerró por inactividad" al llegar al login). */

const CLAVE = "aviso";

export function guardarAviso(mensaje: string) {
  try {
    sessionStorage.setItem(CLAVE, mensaje);
  } catch {
    /* si el navegador no lo permite, simplemente no se muestra */
  }
}

export function tomarAviso(): string | null {
  try {
    const mensaje = sessionStorage.getItem(CLAVE);
    sessionStorage.removeItem(CLAVE);
    return mensaje;
  } catch {
    return null;
  }
}
