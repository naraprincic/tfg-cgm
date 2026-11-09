"use client";

/** Configuración del rango objetivo y las preferencias (HU-004). */

import { useEffect, useState } from "react";
import { Alerta } from "@/components/Formulario";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, ErrorApi, type Configuracion } from "@/lib/api";

const ZONAS = [
  ["America/Argentina/Buenos_Aires", "Argentina (UTC−3)"],
  ["America/Montevideo", "Uruguay (UTC−3)"],
  ["America/Santiago", "Chile"],
  ["America/Sao_Paulo", "Brasil – San Pablo (UTC−3)"],
  ["America/Mexico_City", "México – Ciudad de México"],
  ["Europe/Madrid", "España – Madrid"],
  ["UTC", "UTC"],
];

export default function PaginaConfiguracion() {
  const manejarSesion = useManejarSesionVencida();
  const [form, setForm] = useState<{ rango_min: string; rango_max: string; zona_horaria: string } | null>(null);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api<Configuracion>("/configuracion")
      .then((c) => setForm({ rango_min: String(c.rango_min), rango_max: String(c.rango_max), zona_horaria: c.zona_horaria }))
      .catch((e) => {
        if (!manejarSesion(e)) setMensaje({ tipo: "error", texto: e instanceof Error ? e.message : "Error inesperado." });
      });
  }, [manejarSesion]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setErrores({});
    setMensaje(null);
    setGuardando(true);
    try {
      const r = await api<{ mensaje: string }>("/configuracion", {
        method: "PUT",
        body: JSON.stringify({ rango_min: Number(form.rango_min), rango_max: Number(form.rango_max), zona_horaria: form.zona_horaria }),
      });
      setMensaje({ tipo: "ok", texto: r.mensaje });
    } catch (err) {
      if (err instanceof ErrorApi && err.errores.length) {
        setErrores(Object.fromEntries(err.errores.map((x) => [x.campo, x.mensaje])));
        setMensaje({ tipo: "error", texto: "No se guardaron los cambios: revisá los valores. Se conservan los anteriores." });
      } else if (!manejarSesion(err)) {
        setMensaje({ tipo: "error", texto: err instanceof Error ? err.message : "Error inesperado." });
      }
    } finally {
      setGuardando(false);
    }
  }

  if (!form) return mensaje ? <Alerta tipo="error">{mensaje.texto}</Alerta> : <p className="text-suave">Cargando…</p>;

  const campo = "w-full rounded-lg border border-borde bg-white px-3 py-2.5 outline-none focus:border-marca";

  return (
    <div className="mx-auto max-w-2xl">
      <section className="rounded-xl border border-borde bg-white p-6">
        <h2 className="mb-1 text-lg font-semibold text-marca">Rango objetivo personal</h2>
        <p className="mb-5 text-sm text-suave">
          Se usa para el tiempo en tu rango personal, la banda del gráfico y la detección de períodos fuera de rango.
          Los indicadores del consenso internacional siempre usan 54, 70, 180 y 250 mg/dL. Definí tu rango con tu
          profesional de la salud.
        </p>
        {mensaje && <Alerta tipo={mensaje.tipo}>{mensaje.texto}</Alerta>}
        {errores.general && <Alerta tipo="error">{errores.general}</Alerta>}
        <form onSubmit={guardar} noValidate>
          <div className="mb-4 grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="rango_min" className="mb-1.5 block text-suave">Límite inferior (mg/dL)</label>
              <input id="rango_min" type="number" min={40} max={300} value={form.rango_min} onChange={(e) => setForm({ ...form, rango_min: e.target.value })} className={campo} aria-invalid={errores.rango_min ? true : undefined} />
              {errores.rango_min && <p className="mt-1 text-sm text-error">{errores.rango_min}</p>}
            </div>
            <div>
              <label htmlFor="rango_max" className="mb-1.5 block text-suave">Límite superior (mg/dL)</label>
              <input id="rango_max" type="number" min={40} max={300} value={form.rango_max} onChange={(e) => setForm({ ...form, rango_max: e.target.value })} className={campo} aria-invalid={errores.rango_max ? true : undefined} />
              {errores.rango_max && <p className="mt-1 text-sm text-error">{errores.rango_max}</p>}
            </div>
          </div>
          <div className="mb-6">
            <label htmlFor="zona" className="mb-1.5 block text-suave">Zona horaria</label>
            <select id="zona" value={form.zona_horaria} onChange={(e) => setForm({ ...form, zona_horaria: e.target.value })} className={campo}>
              {ZONAS.map(([valor, nombre]) => (
                <option key={valor} value={valor}>{nombre}</option>
              ))}
            </select>
            <p className="mt-1 text-sm text-suave">Los archivos de los sensores no indican la zona: las horas se interpretan con esta.</p>
          </div>
          <button type="submit" disabled={guardando} className="rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro disabled:opacity-60">
            {guardando ? "Guardando y recalculando…" : "Guardar"}
          </button>
        </form>
      </section>
    </div>
  );
}
