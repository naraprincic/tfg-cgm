"use client";

/** Historial de días procesados (HU-014) – Figura 10 de la tesis. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Alerta } from "@/components/Formulario";
import { Tarjeta } from "@/components/Indicadores";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, type Historial } from "@/lib/api";
import { fechaCorta, nombreDelDia, numero, porcentaje, sumarDias } from "@/lib/fechas";

export default function PaginaHistorial() {
  const router = useRouter();
  const manejarSesion = useManejarSesionVencida();
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [datos, setDatos] = useState<Historial | null>(null);
  const [error, setError] = useState<string | null>(null);

  const consultar = useCallback(
    (d: string, h: string) => {
      const p = new URLSearchParams();
      if (d) p.set("desde", d);
      if (h) p.set("hasta", h);
      return api<Historial>(`/dias?${p}`)
        .then(setDatos)
        .catch((e) => {
          if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
        });
    },
    [manejarSesion],
  );

  // Al entrar: los últimos 30 días con datos.
  useEffect(() => {
    api<Historial>("/dias")
      .then((todo) => {
        const ultimo = todo.dias[0]?.fecha;
        if (!ultimo) return setDatos(todo);
        const inicio = sumarDias(ultimo, -29);
        setDesde(inicio);
        setHasta(ultimo);
        return consultar(inicio, ultimo);
      })
      .catch((e) => {
        if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
      });
  }, [consultar, manejarSesion]);

  if (error) return <Alerta tipo="error">{error}</Alerta>;

  return (
    <div className="mx-auto max-w-6xl">
      <form
        className="mb-5 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          consultar(desde, hasta);
        }}
      >
        <label className="text-sm text-suave">
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="mt-1 block rounded-lg border border-borde bg-white px-3 py-2 text-texto" />
        </label>
        <label className="text-sm text-suave">
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="mt-1 block rounded-lg border border-borde bg-white px-3 py-2 text-texto" />
        </label>
        <button type="submit" className="rounded-lg bg-marca px-4 py-2.5 font-medium text-white hover:bg-marca-oscuro">
          Consultar
        </button>
      </form>

      {datos === null ? (
        <p className="text-suave">Cargando…</p>
      ) : datos.dias.length === 0 ? (
        <div className="rounded-xl border border-borde bg-white p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-marca">No hay días procesados en ese período</h2>
          <p className="text-suave">Probá ampliar el rango de fechas o importá un archivo de mediciones.</p>
        </div>
      ) : (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tarjeta titulo="Días en el período" valor={String(datos.dias.length)} />
            <Tarjeta
              titulo="Tiempo en rango medio"
              valor={porcentaje(datos.dias.reduce((s, d) => s + d.tir, 0) / datos.dias.length)}
              detalle="promedio de los días"
            />
            <Tarjeta
              titulo="Glucosa promedio"
              valor={numero(Math.round(datos.dias.reduce((s, d) => s + d.glucosa_promedio, 0) / datos.dias.length))}
              detalle="mg/dL"
            />
            <Tarjeta titulo="GMI" valor={datos.gmi != null ? `${numero(datos.gmi)} %` : "—"} detalle={datos.gmi_detalle} />
          </div>

          <section className="rounded-xl border border-borde bg-white p-5">
            <h2 className="mb-3 text-lg font-semibold text-marca">Días procesados</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b-2 border-borde text-xs uppercase tracking-wide text-suave">
                    <th className="px-2 py-2">Día</th>
                    <th className="px-2 py-2 text-right">TIR</th>
                    <th className="px-2 py-2 text-right">Bajo</th>
                    <th className="px-2 py-2 text-right">Sobre</th>
                    <th className="px-2 py-2 text-right">Promedio</th>
                    <th className="px-2 py-2 text-right">CV</th>
                    <th className="px-2 py-2 text-right">Cobertura</th>
                    <th className="px-2 py-2">Resumen</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.dias.map((d) => (
                    <tr
                      key={d.fecha}
                      onClick={() => router.push(`/detalle?fecha=${d.fecha}`)}
                      className="cursor-pointer border-b border-borde hover:bg-fondo"
                    >
                      <td className="px-2 py-2.5">
                        <Link href={`/detalle?fecha=${d.fecha}`} className="font-medium text-marca hover:underline">
                          {fechaCorta(d.fecha)}
                        </Link>
                        <span className="ml-2 hidden text-xs text-suave sm:inline">{nombreDelDia(d.fecha, false).split(",")[0]}</span>
                      </td>
                      <td className="px-2 py-2.5 text-right font-semibold">{porcentaje(d.tir)}</td>
                      <td className="px-2 py-2.5 text-right">{porcentaje(d.tbr)}</td>
                      <td className="px-2 py-2.5 text-right">{porcentaje(d.tar)}</td>
                      <td className="px-2 py-2.5 text-right">{numero(Math.round(d.glucosa_promedio))}</td>
                      <td className="px-2 py-2.5 text-right">{porcentaje(d.coeficiente_variacion)}</td>
                      <td className="px-2 py-2.5 text-right">
                        {porcentaje(d.cobertura)}
                        {d.parcial && <span className="ml-1.5 rounded bg-aviso-fondo px-1.5 py-0.5 text-xs text-aviso">parcial</span>}
                      </td>
                      <td className="px-2 py-2.5">
                        <Link href={`/detalle?fecha=${d.fecha}#resumen`} onClick={(e) => e.stopPropagation()} className="text-sm font-medium hover:underline">
                          {d.estado_resumen === "desactualizado" ? (
                            <span className="text-error">Desactualizado</span>
                          ) : d.tiene_resumen ? (
                            <span className="text-marca">Ver{d.estado_resumen === "plantilla" ? " (plantilla)" : ""}</span>
                          ) : (
                            <span className="text-suave">Generar</span>
                          )}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
