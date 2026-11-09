"use client";

/** Detalle del día (HU-010, HU-011, HU-012 y HU-013) – Figuras 9 y 10 de la tesis. */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EtiquetaTipo, TextoAsociacion } from "@/components/Eventos";
import { Alerta } from "@/components/Formulario";
import GraficoGlucosa from "@/components/GraficoGlucosa";
import { IndicadoresCompletos } from "@/components/Indicadores";
import Semaforo from "@/components/Semaforo";
import TarjetaResumen from "@/components/TarjetaResumen";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, ErrorApi, type DetalleDia, type Historial } from "@/lib/api";
import { cantidadTexto, PERIODOS } from "@/lib/eventos";
import { fechaCorta, hoy, nombreDelDia } from "@/lib/fechas";

type Estado =
  | { tipo: "cargando" }
  | { tipo: "sin-datos"; fecha: string }
  | { tipo: "listo"; detalle: DetalleDia };

export default function DetalleDelDia() {
  const router = useRouter();
  const parametros = useSearchParams();
  const manejarSesion = useManejarSesionVencida();
  const fechaPedida = parametros.get("fecha");
  const [fecha, setFecha] = useState<string | null>(fechaPedida);
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando" });
  const [error, setError] = useState<string | null>(null);

  const informar = useCallback(
    (e: unknown) => {
      if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
    },
    [manejarSesion],
  );

  // Sin fecha en la dirección: se abre el último día procesado.
  useEffect(() => {
    if (fechaPedida) return;
    api<Historial>("/dias")
      .then((h) => (h.dias.length ? setFecha(h.dias[0].fecha) : setEstado({ tipo: "sin-datos", fecha: "" })))
      .catch(informar);
  }, [fechaPedida, informar]);

  useEffect(() => {
    if (!fecha) return;
    api<DetalleDia>(`/dias/${fecha}`)
      .then((detalle) => setEstado({ tipo: "listo", detalle }))
      .catch((e) => {
        if (e instanceof ErrorApi && e.estado === 404) setEstado({ tipo: "sin-datos", fecha });
        else informar(e);
      });
  }, [fecha, informar]);

  function irA(nueva: string) {
    setFecha(nueva);
    router.replace(`/detalle?fecha=${nueva}`);
  }

  if (error) return <Alerta tipo="error">{error}</Alerta>;

  const selector = (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      {estado.tipo === "listo" && (
        <button
          type="button"
          disabled={!estado.detalle.dia_anterior}
          onClick={() => estado.detalle.dia_anterior && irA(estado.detalle.dia_anterior)}
          className="rounded-lg border border-borde bg-white px-3 py-2 text-sm disabled:opacity-40"
          aria-label="Día anterior"
        >
          ←
        </button>
      )}
      <input
        type="date"
        value={fecha ?? ""}
        max={hoy()}
        onChange={(e) => e.target.value && irA(e.target.value)}
        className="rounded-lg border border-borde bg-white px-3 py-2 text-sm"
        aria-label="Elegir día"
      />
      {estado.tipo === "listo" && (
        <button
          type="button"
          disabled={!estado.detalle.dia_siguiente}
          onClick={() => estado.detalle.dia_siguiente && irA(estado.detalle.dia_siguiente)}
          className="rounded-lg border border-borde bg-white px-3 py-2 text-sm disabled:opacity-40"
          aria-label="Día siguiente"
        >
          →
        </button>
      )}
      {estado.tipo === "listo" && <span className="ml-1 text-suave">{nombreDelDia(estado.detalle.fecha)}</span>}
    </div>
  );

  if (estado.tipo === "cargando") return <p className="text-suave">Cargando…</p>;

  if (estado.tipo === "sin-datos") {
    // HU-012, criterio 4: informa y ofrece importar.
    return (
      <div className="mx-auto max-w-5xl">
        {selector}
        <div className="rounded-xl border border-borde bg-white p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-marca">
            {estado.fecha ? `No hay mediciones para el ${fechaCorta(estado.fecha)}` : "Todavía no hay mediciones"}
          </h2>
          <p className="mb-5 text-suave">Importá el archivo de tu sensor que incluya ese día para ver su detalle.</p>
          <Link href="/importar" className="inline-block rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro">
            Importar mediciones
          </Link>
        </div>
      </div>
    );
  }

  const d = estado.detalle;
  return (
    <div className="mx-auto max-w-5xl">
      {selector}

      {d.indicadores ? (
        <>
          <IndicadoresCompletos i={d.indicadores} />
          <p className="mt-2 text-xs text-suave">
            Tiempo en rango, bajo y sobre rango usan los umbrales del consenso internacional (54, 70, 180 y 250 mg/dL).
            &quot;En tu rango personal&quot; usa el rango que configuraste. El GMI se muestra en el historial (requiere 14 días).
          </p>
        </>
      ) : (
        <Alerta tipo="aviso">Este día tiene eventos pero no tiene mediciones importadas.</Alerta>
      )}

      {d.indicadores && (
        <TarjetaResumen
          fecha={d.fecha}
          resumen={d.resumen}
          alActualizar={(resumen) => setEstado({ tipo: "listo", detalle: { ...d, resumen } })}
        />
      )}

      {d.semaforo && <Semaforo s={d.semaforo} />}

      {d.puntos.length > 0 && (
        <section className="mt-5 rounded-xl border border-borde bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold text-marca">Curva de glucosa</h2>
          <GraficoGlucosa
            puntos={d.puntos}
            rangoMin={d.rango_min}
            rangoMax={d.rango_max}
            eventos={d.eventos}
            periodos={d.periodos}
            alto="h-80 sm:h-96"
          />
        </section>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="rounded-xl border border-borde bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold text-marca">Línea temporal de eventos</h2>
          {d.eventos.length === 0 ? (
            <p className="text-suave">
              No hay eventos registrados.{" "}
              <Link href={`/eventos?fecha=${d.fecha}`} className="font-medium text-marca hover:underline">
                Registrar uno
              </Link>
            </p>
          ) : (
            <ol className="relative border-l-2 border-borde pl-5">
              {d.eventos.map((e) => (
                <li key={e.id_evento} className="mb-4 last:mb-0">
                  <span className="absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-marca" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-marca">
                      {e.hora_aproximada ? "≈ " : ""}
                      {e.hora}
                    </span>
                    <EtiquetaTipo tipo={e.tipo} />
                    <span>
                      {e.descripcion}
                      {e.cantidad != null && ` — ${cantidadTexto(e.cantidad, e.unidad)}`}
                    </span>
                  </div>
                  <TextoAsociacion evento={e} />
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="rounded-xl border border-borde bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold text-marca">Períodos relevantes</h2>
          {d.periodos.length === 0 ? (
            <p className="text-suave">No se detectaron períodos fuera de rango ni variaciones rápidas.</p>
          ) : (
            <ul className="text-sm">
              {d.periodos.map((p, i) => (
                <li key={i} className="flex flex-wrap items-baseline gap-x-2 border-b border-borde py-2 last:border-b-0">
                  <span className="w-28 font-medium text-marca">
                    {p.desde}–{p.hasta}
                  </span>
                  <span className="font-medium">{PERIODOS[p.tipo]?.nombre ?? p.tipo}</span>
                  <span className="text-suave">
                    {p.duracion_min} min ·{" "}
                    {p.valor_inicio != null
                      ? `de ${p.valor_inicio} a ${p.valor_fin} mg/dL`
                      : `${p.tipo.startsWith("bajo") ? "mínimo" : "máximo"} ${p.valor_extremo} mg/dL`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
