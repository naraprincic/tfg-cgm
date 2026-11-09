"use client";

/** Resumen diario en lenguaje coloquial (HU-013) – Figura 10 de la tesis. */

import { useState } from "react";
import { Alerta } from "@/components/Formulario";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, type Resumen } from "@/lib/api";
import { nombreDelDia } from "@/lib/fechas";

const ESTADOS: Record<Resumen["estado_verificacion"], { texto: string; clase: string }> = {
  aprobado: { texto: "verificación automática: aprobada", clase: "bg-ok-fondo text-ok" },
  plantilla: { texto: "resumen de plantilla (sin inteligencia artificial)", clase: "bg-aviso-fondo text-aviso" },
  desactualizado: { texto: "desactualizado: cambiaron los datos del día", clase: "bg-error-fondo text-error" },
};

const formatoFecha = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});

export default function TarjetaResumen({
  fecha,
  resumen,
  alActualizar,
}: {
  fecha: string;
  resumen: Resumen | null;
  alActualizar: (r: Resumen) => void;
}) {
  const manejarSesion = useManejarSesionVencida();
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [versiones, setVersiones] = useState<Resumen[] | null>(null);

  async function generar() {
    setError(null);
    setGenerando(true);
    try {
      const nuevo = await api<Resumen>(`/dias/${fecha}/resumen`, { method: "POST" });
      setVersiones(null);
      alActualizar(nuevo);
    } catch (e) {
      if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "No se pudo generar el resumen.");
    } finally {
      setGenerando(false);
    }
  }

  async function copiar() {
    if (!resumen) return;
    try {
      await navigator.clipboard.writeText(resumen.texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setError("No se pudo copiar el texto.");
    }
  }

  async function verVersiones() {
    if (versiones) return setVersiones(null);
    try {
      setVersiones(await api<Resumen[]>(`/dias/${fecha}/resumenes`));
    } catch (e) {
      if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
    }
  }

  const boton = "rounded-lg border border-marca px-4 py-2 text-sm font-medium text-marca hover:bg-activo disabled:opacity-50";

  return (
    <section className="mt-5 rounded-xl border border-borde bg-white p-5" id="resumen">
      <h2 className="mb-1 text-lg font-semibold text-marca">Resumen del {nombreDelDia(fecha, false).toLowerCase()}</h2>
      <p className="mb-3 text-sm text-suave">Texto generado a partir de los indicadores y eventos ya calculados por el sistema</p>
      {error && <Alerta tipo="error">{error}</Alerta>}

      {!resumen ? (
        <div>
          <p className="mb-3 text-suave">Todavía no hay un resumen para este día.</p>
          <button type="button" onClick={generar} disabled={generando} className="rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro disabled:opacity-60">
            {generando ? "Generando y verificando…" : "Generar resumen"}
          </button>
        </div>
      ) : (
        <>
          <p className={`leading-relaxed ${resumen.estado_verificacion === "desactualizado" ? "text-suave" : ""}`}>{resumen.texto}</p>
          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-suave">
            <span>Versión {resumen.version}</span>·
            <span>generada el {formatoFecha.format(new Date(resumen.fecha_generacion))}</span>·
            <span>modelo {resumen.modelo_utilizado}</span>·
            <span className={`rounded-full px-2 py-0.5 font-medium ${ESTADOS[resumen.estado_verificacion].clase}`}>
              {ESTADOS[resumen.estado_verificacion].texto}
            </span>
          </p>
          {resumen.estado_verificacion === "plantilla" && resumen.observaciones.length > 0 && (
            <details className="mt-2 text-xs text-suave">
              <summary className="cursor-pointer">¿Por qué se usó la plantilla?</summary>
              <ul className="mt-1 list-disc pl-5">
                {resumen.observaciones.map((o, i) => (
                  <li key={`${i}-${o}`}>{o}</li>
                ))}
              </ul>
            </details>
          )}
          <p className="mt-3 rounded-lg border border-dashed border-borde bg-fondo px-4 py-2.5 text-sm text-suave">{resumen.aviso}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={copiar} className={boton}>{copiado ? "¡Copiado!" : "Copiar"}</button>
            <button type="button" onClick={verVersiones} className={boton}>
              {versiones ? "Ocultar versiones" : "Ver versiones anteriores"}
            </button>
            <button
              type="button"
              onClick={generar}
              disabled={generando}
              className={resumen.estado_verificacion === "desactualizado" ? "rounded-lg bg-marca px-4 py-2 text-sm font-medium text-white hover:bg-marca-oscuro disabled:opacity-60" : boton}
            >
              {generando ? "Generando…" : "Regenerar"}
            </button>
          </div>
          {versiones && (
            <ol className="mt-4 space-y-3 border-t border-borde pt-4">
              {versiones.map((v) => (
                <li key={v.version} className="text-sm">
                  <p className="mb-1 text-xs text-suave">
                    Versión {v.version}{v.vigente ? " (vigente)" : ""} · {formatoFecha.format(new Date(v.fecha_generacion))} ·{" "}
                    {v.modelo_utilizado} · {ESTADOS[v.estado_verificacion].texto} · motivo: {v.motivo_generacion}
                  </p>
                  <p className="text-suave">{v.texto}</p>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  );
}
