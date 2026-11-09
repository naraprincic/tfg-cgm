"use client";

/** Registro de un evento cotidiano – Figura 8 de la tesis. */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EtiquetaTipo } from "@/components/Eventos";
import { Alerta } from "@/components/Formulario";
import RegistroLenguajeNatural from "@/components/RegistroLenguajeNatural";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, ErrorApi, type Evento, type Historial } from "@/lib/api";
import { cantidadTexto, TIPOS, type TipoEvento } from "@/lib/eventos";
import { nombreDelDia } from "@/lib/fechas";

function hoy() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const VACIO = { tipo: "comida" as TipoEvento, descripcion: "", hora: "", aproximada: false, cantidad: "", unidad: "porciones" };

export default function RegistrarEvento() {
  const manejarSesion = useManejarSesionVencida();
  const parametros = useSearchParams();
  const [fecha, setFecha] = useState(parametros.get("fecha") ?? "");
  const [form, setForm] = useState(VACIO);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [advertencia, setAdvertencia] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [eventos, setEventos] = useState<Evento[] | null>(null);

  const informar = useCallback(
    (e: unknown) => {
      if (!manejarSesion(e)) setMensaje({ tipo: "error", texto: e instanceof Error ? e.message : "Error inesperado." });
    },
    [manejarSesion],
  );

  // Sin fecha en la dirección: se propone el último día con mediciones (o hoy).
  useEffect(() => {
    if (fecha) return;
    api<Historial>("/dias")
      .then((h) => setFecha(h.dias[0]?.fecha ?? hoy()))
      .catch(informar);
  }, [fecha, informar]);

  const cargarEventos = useCallback(
    (dia: string) => api<Evento[]>(`/eventos?fecha=${dia}`).then(setEventos).catch(informar),
    [informar],
  );

  useEffect(() => {
    if (fecha) cargarEventos(fecha);
  }, [fecha, cargarEventos]);

  const unidades = TIPOS[form.tipo].unidades;

  function cambiarTipo(tipo: TipoEvento) {
    setForm((f) => ({ ...f, tipo, unidad: TIPOS[tipo].unidades[0] ?? "", cantidad: TIPOS[tipo].unidades.length ? f.cantidad : "" }));
  }

  async function guardar(confirmarSinDatos = false) {
    setErrores({});
    setMensaje(null);
    const faltan: Record<string, string> = {};
    if (!form.descripcion.trim()) faltan.descripcion = "Este campo es obligatorio.";
    if (!fecha) faltan.fecha = "Este campo es obligatorio.";
    if (!form.hora) faltan.hora = "Este campo es obligatorio.";
    if (Object.keys(faltan).length) {
      setErrores(faltan);
      return;
    }
    setGuardando(true);
    try {
      await api<Evento>("/eventos", {
        method: "POST",
        body: JSON.stringify({
          tipo: form.tipo,
          descripcion: form.descripcion,
          fecha_hora: `${fecha}T${form.hora}`,
          hora_aproximada: form.aproximada,
          cantidad: form.cantidad ? Number(form.cantidad.replace(",", ".")) : null,
          unidad: form.cantidad ? form.unidad : null,
          confirmar_sin_datos: confirmarSinDatos,
        }),
      });
      setAdvertencia(null);
      setForm({ ...VACIO, tipo: form.tipo, unidad: form.unidad });
      setMensaje({ tipo: "ok", texto: "Evento guardado." });
      cargarEventos(fecha);
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 409) setAdvertencia(e.message);
      else if (e instanceof ErrorApi && e.errores.length)
        setErrores(Object.fromEntries(e.errores.map((x) => [x.campo === "general" ? "cantidad" : x.campo, x.mensaje])));
      else informar(e);
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar(id: number) {
    try {
      await api(`/eventos/${id}`, { method: "DELETE" });
      cargarEventos(fecha);
    } catch (e) {
      informar(e);
    }
  }

  const campo = "w-full rounded-lg border border-borde bg-white px-3 py-2.5 outline-none focus:border-marca";

  return (
    <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[1.2fr_1fr]">
      <div>
        {fecha && (
          <RegistroLenguajeNatural
            fecha={fecha}
            alGuardar={() => cargarEventos(fecha)}
            alPedirCargaManual={() => {
              const campoDescripcion = document.getElementById("descripcion");
              campoDescripcion?.scrollIntoView({ behavior: "smooth", block: "center" });
              campoDescripcion?.focus();
            }}
          />
        )}

        <section className="rounded-xl border border-borde bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold text-marca">Carga manual</h2>
          {mensaje && <Alerta tipo={mensaje.tipo}>{mensaje.texto}</Alerta>}
          {advertencia && (
            <Alerta tipo="aviso">
              <p className="mb-2">{advertencia}</p>
              <div className="flex gap-2">
                <button type="button" onClick={() => guardar(true)} className="rounded-md bg-aviso px-3 py-1.5 text-white">
                  Guardar igual
                </button>
                <button type="button" onClick={() => setAdvertencia(null)} className="rounded-md border border-aviso px-3 py-1.5">
                  Corregir la fecha
                </button>
              </div>
            </Alerta>
          )}
          <form
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              guardar();
            }}
          >
            <fieldset className="mb-4">
              <legend className="mb-1.5 text-suave">Tipo</legend>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(TIPOS) as TipoEvento[]).map((t) => (
                  <label
                    key={t}
                    className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm ${form.tipo === t ? "border-marca bg-activo font-semibold text-marca" : "border-borde"}`}
                  >
                    <input type="radio" name="tipo" value={t} checked={form.tipo === t} onChange={() => cambiarTipo(t)} className="sr-only" />
                    {TIPOS[t].nombre}
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="mb-4">
              <label htmlFor="descripcion" className="mb-1.5 block text-suave">Descripción</label>
              <input
                id="descripcion"
                maxLength={160}
                value={form.descripcion}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
                placeholder={form.tipo === "comida" ? "Almuerzo: milanesa con puré" : form.tipo === "insulina" ? "Insulina rápida" : form.tipo === "actividad_fisica" ? "Caminata" : ""}
                className={campo}
                aria-invalid={errores.descripcion ? true : undefined}
              />
              {errores.descripcion && <p className="mt-1 text-sm text-error">{errores.descripcion}</p>}
            </div>

            <div className="mb-4 grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="fecha" className="mb-1.5 block text-suave">Fecha</label>
                <input id="fecha" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className={campo} />
                {errores.fecha && <p className="mt-1 text-sm text-error">{errores.fecha}</p>}
              </div>
              <div>
                <label htmlFor="hora" className="mb-1.5 block text-suave">Hora</label>
                <input id="hora" type="time" value={form.hora} onChange={(e) => setForm({ ...form, hora: e.target.value })} className={campo} aria-invalid={errores.hora ? true : undefined} />
                {errores.hora && <p className="mt-1 text-sm text-error">{errores.hora}</p>}
              </div>
            </div>
            <label className="mb-4 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.aproximada} onChange={(e) => setForm({ ...form, aproximada: e.target.checked })} className="h-4 w-4 accent-marca" />
              La hora es aproximada
            </label>

            {unidades.length > 0 && (
              <div className="mb-4 grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="cantidad" className="mb-1.5 block text-suave">Cantidad (opcional)</label>
                  <input id="cantidad" inputMode="decimal" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} className={campo} />
                </div>
                <div>
                  <label htmlFor="unidad" className="mb-1.5 block text-suave">Unidad</label>
                  <select id="unidad" value={form.unidad} onChange={(e) => setForm({ ...form, unidad: e.target.value })} className={campo}>
                    {unidades.map((u) => (
                      <option key={u} value={u}>{u}</option>
                    ))}
                  </select>
                </div>
                {errores.cantidad && <p className="col-span-2 text-sm text-error">{errores.cantidad}</p>}
              </div>
            )}

            <button type="submit" disabled={guardando} className="w-full rounded-lg bg-marca px-4 py-3 font-medium text-white hover:bg-marca-oscuro disabled:opacity-60">
              {guardando ? "Guardando…" : "Guardar evento"}
            </button>
          </form>
        </section>
      </div>

      <section className="h-fit rounded-xl border border-borde bg-white p-5">
        <h2 className="mb-1 text-lg font-semibold text-marca">Eventos del día</h2>
        <p className="mb-3 text-sm text-suave">{fecha ? nombreDelDia(fecha) : ""}</p>
        {eventos === null ? (
          <p className="text-suave">Cargando…</p>
        ) : eventos.length === 0 ? (
          <p className="text-suave">Todavía no hay eventos este día.</p>
        ) : (
          <ul>
            {eventos.map((e) => (
              <li key={e.id_evento} className="flex items-start gap-3 border-b border-borde py-2.5 last:border-b-0">
                <span className="w-12 pt-0.5 font-semibold text-marca">{e.hora_aproximada ? "≈" : ""}{e.hora}</span>
                <div className="flex-1">
                  <EtiquetaTipo tipo={e.tipo} />
                  <p className="mt-1 text-sm">
                    {e.descripcion}
                    {e.cantidad != null && ` — ${cantidadTexto(e.cantidad, e.unidad)}`}
                  </p>
                </div>
                <button type="button" onClick={() => eliminar(e.id_evento)} className="text-sm text-suave hover:text-error" aria-label={`Eliminar ${e.descripcion}`}>
                  Eliminar
                </button>
              </li>
            ))}
          </ul>
        )}
        {fecha && (
          <Link href={`/detalle?fecha=${fecha}`} className="mt-4 inline-block text-sm font-medium text-marca hover:underline">
            Ver el detalle del día →
          </Link>
        )}
      </section>
    </div>
  );
}
