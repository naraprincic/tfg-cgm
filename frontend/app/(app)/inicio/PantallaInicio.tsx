"use client";

/** Pantalla de inicio – Figura 6 de la tesis. */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alerta } from "@/components/Formulario";
import GraficoGlucosa from "@/components/GraficoGlucosa";
import { IndicadoresPrincipales } from "@/components/Indicadores";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import Semaforo from "@/components/Semaforo";
import TarjetaResumen from "@/components/TarjetaResumen";
import { EtiquetaTipo } from "@/components/Eventos";
import { api, ErrorApi, type DetalleDia, type Historial } from "@/lib/api";
import { cantidadTexto } from "@/lib/eventos";
import { fechaCorta, hoy, nombreDelDia, porcentaje } from "@/lib/fechas";

export default function PaginaInicio() {
  const manejarSesion = useManejarSesionVencida();
  const [historial, setHistorial] = useState<Historial | null>(null);
  const [elegido, setElegido] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<DetalleDia | null>(null);
  const [sinDatos, setSinDatos] = useState<string | null>(null); // fecha elegida que no tiene mediciones
  const [error, setError] = useState<string | null>(null);

  const informar = useCallback(
    (e: unknown) => {
      if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
    },
    [manejarSesion],
  );

  useEffect(() => {
    api<Historial>("/dias")
      .then((h) => {
        setHistorial(h);
        if (h.dias.length) setElegido(h.dias[0].fecha); // el último día procesado
      })
      .catch(informar);
  }, [informar]);

  useEffect(() => {
    if (!elegido) return;
    api<DetalleDia>(`/dias/${elegido}`)
      .then((d) => {
        setSinDatos(null);
        setDetalle(d);
      })
      .catch((e) => {
        if (e instanceof ErrorApi && e.estado === 404) setSinDatos(elegido);
        else informar(e);
      });
  }, [elegido, informar]);

  if (error) return <Alerta tipo="error">{error}</Alerta>;
  if (historial === null) return <p className="text-suave">Cargando…</p>;

  if (historial.dias.length === 0) {
    return (
      <div className="mx-auto max-w-xl rounded-xl border border-borde bg-white p-8 text-center">
        <h2 className="mb-2 text-xl font-semibold text-marca">Todavía no hay mediciones</h2>
        <p className="mb-5 text-suave">
          Importá el archivo CSV que exporta la aplicación de tu sensor para ver tu curva de glucosa y tus indicadores.
        </p>
        <Link href="/importar" className="inline-block rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro">
          Importar mediciones
        </Link>
      </div>
    );
  }

  const actual = detalle && detalle.fecha === elegido ? detalle : null;
  // Días con datos, del más nuevo al más viejo: las flechas saltan al día con datos más cercano.
  const fechas = historial.dias.map((d) => d.fecha);
  const anterior = elegido ? fechas.find((f) => f < elegido) ?? null : null;
  const siguiente = elegido ? [...fechas].reverse().find((f) => f > elegido) ?? null : null;
  const ind = actual?.indicadores;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={!anterior}
          onClick={() => anterior && setElegido(anterior)}
          className="rounded-lg border border-borde bg-white px-3 py-2 text-sm disabled:opacity-40"
          aria-label="Día anterior"
        >
          ←
        </button>
        <input
          type="date"
          value={elegido ?? ""}
          max={hoy()}
          onChange={(e) => e.target.value && setElegido(e.target.value)}
          className="rounded-lg border border-borde bg-white px-3 py-2 text-sm"
          aria-label="Elegir día"
        />
        <button
          type="button"
          disabled={!siguiente}
          onClick={() => siguiente && setElegido(siguiente)}
          className="rounded-lg border border-borde bg-white px-3 py-2 text-sm disabled:opacity-40"
          aria-label="Día siguiente"
        >
          →
        </button>
        <span className="ml-1 text-suave">
          {elegido && nombreDelDia(elegido)}
          {ind && ` · ${ind.mediciones_validas} mediciones · cobertura ${porcentaje(ind.cobertura)}`}
        </span>
      </div>

      {sinDatos && sinDatos === elegido ? (
        <div className="rounded-xl border border-borde bg-white p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-marca">No hay mediciones para el {fechaCorta(sinDatos)}</h2>
          <p className="mb-5 text-suave">Elegí otro día o importá el archivo de tu sensor que incluya esa fecha.</p>
          <Link href="/importar" className="inline-block rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro">
            Importar mediciones
          </Link>
        </div>
      ) : !actual ? (
        <p className="text-suave">Cargando…</p>
      ) : (
        <>
          {ind && <IndicadoresPrincipales i={ind} />}
          {ind?.parcial && (
            <p className="mt-2 text-sm text-aviso">
              Día con datos parciales: la cobertura es menor al 70 %, los indicadores son orientativos.
            </p>
          )}

          {ind && (
            <TarjetaResumen
              fecha={actual.fecha}
              resumen={actual.resumen}
              alActualizar={(resumen) => setDetalle({ ...actual, resumen })}
            />
          )}

          <section className="mt-5 rounded-xl border border-borde bg-white p-5">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-semibold text-marca">Tu glucosa del día</h2>
              <Link href={`/detalle?fecha=${actual.fecha}`} className="text-sm font-medium text-marca hover:underline">
                Ver detalle del día →
              </Link>
            </div>
            <GraficoGlucosa
              puntos={actual.puntos}
              rangoMin={actual.rango_min}
              rangoMax={actual.rango_max}
              eventos={actual.eventos}
            />
          </section>

          {actual.semaforo && <Semaforo s={actual.semaforo} />}


          <section className="mt-5 rounded-xl border border-borde bg-white p-5">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-semibold text-marca">Eventos del día</h2>
              <Link href={`/eventos?fecha=${actual.fecha}`} className="text-sm font-medium text-marca hover:underline">
                Registrar evento →
              </Link>
            </div>
            {actual.eventos.length === 0 ? (
              <p className="text-suave">No hay eventos registrados para este día.</p>
            ) : (
              <ul>
                {[...actual.eventos].reverse().map((e) => (
                  <li key={e.id_evento} className="flex flex-wrap items-center gap-3 border-b border-borde py-2.5 last:border-b-0">
                    <span className="w-12 font-semibold text-marca">{e.hora}</span>
                    <EtiquetaTipo tipo={e.tipo} />
                    <span>
                      {e.descripcion}
                      {e.cantidad != null && ` — ${cantidadTexto(e.cantidad, e.unidad)}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
