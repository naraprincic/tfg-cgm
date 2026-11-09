"use client";

/** Pantalla de registro (HU-001), con el consentimiento de la Ley 25.326. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alerta, BotonPrincipal, Campo, Tarjeta } from "@/components/Formulario";
import { api, ErrorApi } from "@/lib/api";
import { guardarAviso } from "@/lib/avisos";

export default function PaginaRegistro() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [consentimiento, setConsentimiento] = useState(false);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErrores({});
    setMensaje(null);
    setCargando(true);
    try {
      await api("/auth/registro", {
        method: "POST",
        body: JSON.stringify({ email, contrasena, acepta_consentimiento: consentimiento }),
      });
      guardarAviso("Cuenta creada correctamente. Ya podés iniciar sesión.");
      router.push("/login");
    } catch (error) {
      if (error instanceof ErrorApi && error.errores.length) {
        setErrores(Object.fromEntries(error.errores.map((x) => [x.campo, x.mensaje])));
        setMensaje("Revisá los campos marcados.");
      } else {
        setMensaje(error instanceof Error ? error.message : "Ocurrió un error inesperado.");
      }
    } finally {
      setCargando(false);
    }
  }

  return (
    <Tarjeta titulo="Crear cuenta">
      {mensaje && <Alerta tipo="error">{mensaje}</Alerta>}
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
          autoComplete="new-password"
          value={contrasena}
          onChange={(e) => setContrasena(e.target.value)}
          error={errores.contrasena}
          ayuda="Entre 8 y 64 caracteres, con al menos una mayúscula, una minúscula y un número. No puede incluir tu correo."
        />

        <div className="mb-2 mt-5 rounded-lg border border-borde bg-fondo p-4 text-sm text-suave">
          <p className="mb-2 font-semibold text-texto">Tratamiento de tus datos de salud</p>
          <p>
            La aplicación guarda tus mediciones de glucosa y los eventos que registres para mostrártelos
            organizados. Son datos sensibles (Ley 25.326): se almacenan protegidos, solo vos podés verlos
            y podés pedir su eliminación cuando quieras. La aplicación no realiza diagnósticos ni indica
            tratamientos.
          </p>
        </div>
        <label className="mb-1 flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            name="acepta_consentimiento"
            checked={consentimiento}
            onChange={(e) => setConsentimiento(e.target.checked)}
            aria-invalid={errores.acepta_consentimiento ? true : undefined}
            className="mt-0.5 h-5 w-5 accent-marca"
          />
          <span>Acepto de forma expresa el tratamiento de mis datos de salud.</span>
        </label>
        {errores.acepta_consentimiento && (
          <p className="mb-2 text-sm text-error">{errores.acepta_consentimiento}</p>
        )}

        <div className="mt-6">
          <BotonPrincipal type="submit" cargando={cargando}>
            Crear cuenta
          </BotonPrincipal>
        </div>
      </form>
      <p className="mt-6 text-center text-suave">
        ¿Ya tenés cuenta?{" "}
        <Link href="/login" className="font-semibold text-marca hover:underline">
          Iniciá sesión
        </Link>
      </p>
    </Tarjeta>
  );
}
