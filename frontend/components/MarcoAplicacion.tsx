"use client";

/** Marco de las pantallas privadas: encabezado, menú lateral y control de sesión. */

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ErrorApi, type Usuario } from "@/lib/api";
import { guardarAviso } from "@/lib/avisos";

const ContextoUsuario = createContext<Usuario | null>(null);

/** Devuelve el usuario con sesión iniciada (solo dentro de las pantallas privadas). */
export function useUsuario(): Usuario {
  const usuario = useContext(ContextoUsuario);
  if (!usuario) throw new Error("useUsuario se usa fuera del marco de la aplicación");
  return usuario;
}

/** Para las pantallas: si un pedido responde 401, lleva al login con el motivo. */
export function useManejarSesionVencida() {
  const router = useRouter();
  return useCallback(
    (error: unknown) => {
      if (error instanceof ErrorApi && error.estado === 401) {
        guardarAviso(error.message);
        router.replace("/login");
        return true;
      }
      return false;
    },
    [router],
  );
}

const MENU = [
  { href: "/inicio", texto: "Inicio" },
  { href: "/importar", texto: "Importar mediciones" },
  { href: "/eventos", texto: "Registrar evento" },
  { href: "/detalle", texto: "Detalle del día" },
  { href: "/historial", texto: "Historial" },
  { href: "/configuracion", texto: "Configuración" },
];

const TITULOS: Record<string, string> = Object.fromEntries(MENU.map((m) => [m.href, m.texto]));

export default function MarcoAplicacion({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ruta = usePathname();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [menuAbierto, setMenuAbierto] = useState(false);

  useEffect(() => {
    const sinSesion = (error: unknown) => {
      setUsuario(null);
      if (error instanceof ErrorApi && error.estado === 401) {
        if (error.message.includes("inactividad")) guardarAviso(error.message);
      } else {
        guardarAviso(error instanceof Error ? error.message : "Error inesperado.");
      }
      router.replace("/login");
    };
    const comprobar = () => api<Usuario>("/auth/yo").then(setUsuario).catch(sinSesion);

    comprobar();
    // Si el navegador muestra la página desde su caché (botón "atrás"), se vuelve a comprobar.
    const alMostrar = (e: PageTransitionEvent) => {
      if (e.persisted) comprobar();
    };
    window.addEventListener("pageshow", alMostrar);
    return () => window.removeEventListener("pageshow", alMostrar);
  }, [router]);

  async function cerrarSesion() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUsuario(null);
    router.replace("/login");
  }

  if (!usuario) {
    return (
      <div className="flex flex-1 items-center justify-center text-suave" role="status">
        Cargando…
      </div>
    );
  }

  const inicial = usuario.email.charAt(0).toUpperCase();

  return (
    <ContextoUsuario.Provider value={usuario}>
      <div className="flex min-h-screen flex-col">
        <header className="flex items-center justify-between gap-3 bg-marca px-4 py-3 text-white sm:px-7 sm:py-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded p-1 md:hidden"
              aria-label="Abrir menú"
              aria-expanded={menuAbierto}
              onClick={() => setMenuAbierto((v) => !v)}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <Image src="/logo.png" alt="" width={40} height={40} priority className="h-9 w-9 rounded-full sm:h-10 sm:w-10" />
            <h1 className="text-lg font-semibold sm:text-xl">{TITULOS[ruta] ?? "Glucosa"}</h1>
          </div>
          <div className="flex items-center gap-3">
            <span
              className="flex h-8 w-8 items-center justify-center rounded-full bg-activo-borde text-sm font-semibold text-marca-oscuro"
              aria-hidden
            >
              {inicial}
            </span>
            <span className="hidden max-w-[16rem] truncate text-sm sm:inline">{usuario.email}</span>
            <button
              type="button"
              onClick={cerrarSesion}
              className="rounded-md border border-white/40 px-3 py-1.5 text-sm hover:bg-white/10"
            >
              Cerrar sesión
            </button>
          </div>
        </header>

        <div className="flex flex-1">
          <nav
            aria-label="Menú principal"
            className={`${menuAbierto ? "block" : "hidden"} absolute inset-x-0 top-[56px] z-10 border-b border-borde bg-fondo md:static md:block md:w-56 md:shrink-0 md:border-b-0 md:border-r`}
          >
            <ul className="py-4">
              {MENU.map((item) => {
                const activo = ruta === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => setMenuAbierto(false)}
                      aria-current={activo ? "page" : undefined}
                      className={`block border-l-4 px-6 py-3 ${
                        activo
                          ? "border-activo-borde bg-activo font-semibold text-marca"
                          : "border-transparent text-texto hover:bg-white"
                      }`}
                    >
                      {item.texto}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <main className="min-w-0 flex-1 px-4 py-6 sm:px-8">{children}</main>
        </div>

        <footer className="px-6 py-3 text-right text-xs text-suave">
          Prototipo académico con datos sintéticos. No realiza diagnósticos ni indica tratamientos.
        </footer>
      </div>
    </ContextoUsuario.Provider>
  );
}
