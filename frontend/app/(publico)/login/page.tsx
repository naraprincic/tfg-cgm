"use client";

/** Pantalla de inicio de sesión (HU-002) – Figura 5 de la tesis. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alerta, BotonPrincipal, Campo, Tarjeta } from "@/components/Formulario";
import { api, ErrorApi } from "@/lib/api";
import { tomarAviso } from "@/lib/avisos";

// Cuenta de prueba de la demo en línea (se configura en Vercel; en la compu no se muestra).
const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL;
const DEMO_CONTRASENA = process.env.NEXT_PUBLIC_DEMO_CONTRASENA;

/** En la demo gratuita el servidor se "duerme" tras 15 minutos sin uso y tarda cerca de un minuto en despertar. */
function useServidorDespierto() {
  const [despertando, setDespertando] = useState(false);
  useEffect(() => {
    let cancelado = false;
    const aviso = setTimeout(() => !cancelado && setDespertando(true), 2500);
    (async () => {
      for (let intento = 0; intento < 30 && !cancelado; intento++) {
        try {
          const r = await fetch("/api/salud", { cache: "no-store" });
          if (r.ok) break;
        } catch {
          // todavía no responde: se reintenta
        }
        await new Promise((listo) => setTimeout(listo, 4000));
      }
      clearTimeout(aviso);
      if (!cancelado) setDespertando(false);
    })();
    return () => {
      cancelado = true;
      clearTimeout(aviso);
    };
  }, []);
  return despertando;
}

export default function PaginaLogin() {
  const despertando = useServidorDespierto();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    // Mensaje que dejó otra pantalla (cuenta creada, sesión cerrada por inactividad...).
    // Se lee al montar porque sessionStorage solo existe en el navegador.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAviso(tomarAviso());
  }, []);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErrores({});
    setMensaje(null);
    setAviso(null);
    setCargando(true);
    try {
      await api("/auth/login", { method: "POST", body: JSON.stringify({ email, contrasena }) });
      router.replace("/inicio");
    } catch (error) {
      if (error instanceof ErrorApi && error.errores.length) {
        setErrores(Object.fromEntries(error.errores.map((x) => [x.campo, x.mensaje])));
      } else {
        setMensaje(error instanceof Error ? error.message : "Ocurrió un error inesperado.");
      }
    } finally {
      setCargando(false);
    }
  }

  return (
    <Tarjeta titulo="Iniciar sesión">
      {aviso && <Alerta tipo={aviso.includes("creada") ? "ok" : "aviso"}>{aviso}</Alerta>}
      {mensaje && <Alerta tipo="error">{mensaje}</Alerta>}
      {despertando && (
        <Alerta tipo="aviso">Despertando el servidor de la demostración: puede tardar hasta un minuto. Esperá un momento…</Alerta>
      )}
      {DEMO_EMAIL && DEMO_CONTRASENA && (
        <div className="mb-5 rounded-lg border border-activo-borde bg-activo/60 px-4 py-3 text-sm">
          <p className="font-semibold text-marca">Cuenta de prueba con datos cargados</p>
          <p className="mt-1">
            Correo: <span className="font-medium">{DEMO_EMAIL}</span> · Contraseña: <span className="font-medium">{DEMO_CONTRASENA}</span>
          </p>
          <button
            type="button"
            onClick={() => {
              setEmail(DEMO_EMAIL);
              setContrasena(DEMO_CONTRASENA);
            }}
            className="mt-2 font-semibold text-marca hover:underline"
          >
            Completar con la cuenta de prueba
          </button>
        </div>
      )}
      <form onSubmit={enviar} noValidate>
        <Campo
          id="email"
          etiqueta="Correo electrónico"
          type="email"
          autoComplete="email"
          placeholder="nombre@correo.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errores.email}
        />
        <Campo
          id="contrasena"
          etiqueta="Contraseña"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={contrasena}
          onChange={(e) => setContrasena(e.target.value)}
          error={errores.contrasena}
        />
        <div className="mt-6">
          <BotonPrincipal type="submit" cargando={cargando}>
            Ingresar
          </BotonPrincipal>
        </div>
      </form>
      <p className="mt-6 text-center text-suave">
        ¿No tenés cuenta?{" "}
        <Link href="/registro" className="font-semibold text-marca hover:underline">
          Registrate
        </Link>
      </p>
    </Tarjeta>
  );
}
