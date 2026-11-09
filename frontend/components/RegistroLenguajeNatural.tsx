"use client";

/** Registro en lenguaje natural (HU-008) – Figura 8 de la tesis. */

import { useEffect, useState } from "react";
import { Alerta } from "@/components/Formulario";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, ErrorApi, type Borrador, type EstadoIA, type Interpretacion } from "@/lib/api";
import { TIPOS, type TipoEvento } from "@/lib/eventos";

type Fila = {
  id_evento: number;
  tipo: TipoEvento;
  descripcion: string;
  hora: string;
  fecha: string;
  cantidad: string;
  unidad: string;
  hora_propuesta: boolean;
  hora_aproximada: boolean;
};

function aFila(b: Borrador, fechaPorDefecto: string): Fila {
  const fecha = b.fecha;
  return {
    id_evento: b.id_evento,
    tipo: b.tipo as TipoEvento,
    descripcion: b.descripcion,
    hora: b.hora,
    fecha: fecha || fechaPorDefecto,
    cantidad: b.cantidad != null ? String(b.cantidad) : "",
    unidad: b.unidad ?? TIPOS[b.tipo as TipoEvento]?.unidades[0] ?? "",
    hora_propuesta: b.hora_propuesta,
    hora_aproximada: b.hora_aproximada,
  };
}

export default function RegistroLenguajeNatural({
  fecha,
  alGuardar,
  alPedirCargaManual,
}: {
  fecha: string;
  alGuardar: () => void;
  alPedirCargaManual: () => void;
}) {
  const manejarSesion = useManejarSesionVencida();
  const [ia, setIa] = useState<EstadoIA | null>(null);
  const [texto, setTexto] = useState("");
  const [filas, setFilas] = useState<Fila[] | null>(null);
  const [advertencias, setAdvertencias] = useState<string[]>([]);
  const [estado, setEstado] = useState<"libre" | "interpretando" | "confirmando">("libre");
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error" | "aviso"; texto: string } | null>(null);

  useEffect(() => {
    api<EstadoIA>("/ia/estado").then(setIa).catch(() => setIa({ disponible: false, modelo: "" }));
  }, []);

  async function interpretar() {
    setMensaje(null);
    if (!texto.trim()) {
      setMensaje({ tipo: "error", texto: "Escribí qué pasó para poder interpretarlo." });
      return;
    }
    setEstado("interpretando");
    try {
      const r = await api<Interpretacion>("/eventos/interpretar", {
        method: "POST",
        body: JSON.stringify({ texto, fecha }),
      });
      setFilas(r.borradores.map((b) => aFila(b, fecha)));
      setAdvertencias(r.borradores.flatMap((b, i) => b.advertencias.map((a) => `${TIPOS[b.tipo as TipoEvento]?.nombre ?? b.tipo} (fila ${i + 1}): ${a}`)));
    } catch (e) {
      if (manejarSesion(e)) return;
      // Servicio caído o interpretación fallida: el texto queda escrito (HU-008, criterio 5).
      setMensaje({ tipo: "aviso", texto: e instanceof Error ? e.message : "No se pudo interpretar el texto." });
    } finally {
      setEstado("libre");
    }
  }

  function cambiar(i: number, cambios: Partial<Fila>) {
    setFilas((actual) => actual && actual.map((f, j) => (j === i ? { ...f, ...cambios } : f)));
  }

  async function confirmar() {
    if (!filas) return;
    setMensaje(null);
    setEstado("confirmando");
    try {
      await api("/eventos/confirmar", {
        method: "POST",
        body: JSON.stringify({
          eventos: filas.map((f) => ({
            id_evento: f.id_evento,
            tipo: f.tipo,
            descripcion: f.descripcion,
            fecha_hora: `${f.fecha}T${f.hora}`,
            hora_aproximada: f.hora_aproximada,
            cantidad: f.cantidad ? Number(f.cantidad.replace(",", ".")) : null,
            unidad: f.cantidad ? f.unidad : null,
          })),
        }),
      });
      setMensaje({ tipo: "ok", texto: `Se ${filas.length === 1 ? "guardó 1 evento" : `guardaron ${filas.length} eventos`} con el texto original.` });
      setFilas(null);
      setAdvertencias([]);
      setTexto("");
      alGuardar();
    } catch (e) {
      if (manejarSesion(e)) return;
      const detalle = e instanceof ErrorApi && e.errores.length ? e.errores.map((x) => x.mensaje).join(" ") : e instanceof Error ? e.message : "";
      setMensaje({ tipo: "error", texto: `No se pudieron confirmar: ${detalle} Corregí los campos y volvé a intentar.` });
    } finally {
      setEstado("libre");
    }
  }

  async function descartar() {
    if (!filas) return;
    await api("/eventos/descartar", { method: "POST", body: JSON.stringify({ ids: filas.map((f) => f.id_evento) }) }).catch(() => undefined);
    setFilas(null);
    setAdvertencias([]);
    setMensaje({ tipo: "aviso", texto: "Se descartó la interpretación. Tu texto sigue escrito por si querés corregirlo." });
  }

  const campo = "w-full rounded-md border border-borde bg-white px-2 py-1.5 text-sm outline-none focus:border-marca";

  return (
    <>
      <section className="mb-5 rounded-xl border border-borde bg-white p-5">
        <h2 className="mb-3 text-lg font-semibold text-marca">Contame qué pasó</h2>
        {ia && !ia.disponible && (
          <Alerta tipo="aviso">
            La interpretación con inteligencia artificial no está configurada (falta la clave de OpenAI en el archivo
            .env del backend). Mientras tanto, podés cargar los eventos manualmente.
          </Alerta>
        )}
        {mensaje && <Alerta tipo={mensaje.tipo}>{mensaje.texto}</Alerta>}
        <label htmlFor="texto-natural" className="sr-only">Describí lo que pasó</label>
        <textarea
          id="texto-natural"
          rows={3}
          maxLength={1000}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Por ejemplo: almorcé milanesa con puré a las 13 menos diez, me puse 6 unidades de rápida y a las 4 de la tarde salí a caminar como 40 minutos."
          className="w-full rounded-lg border border-borde px-3 py-2.5 outline-none focus:border-marca"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={interpretar}
            disabled={estado !== "libre" || ia?.disponible === false}
            className="rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro disabled:opacity-50"
          >
            {estado === "interpretando" ? "Interpretando…" : "Interpretar"}
          </button>
          <button type="button" onClick={alPedirCargaManual} className="rounded-lg border border-marca px-5 py-2.5 font-medium text-marca hover:bg-activo">
            Cargar manualmente
          </button>
        </div>
      </section>

      {filas && (
        <section className="mb-5 rounded-xl border border-borde bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold text-marca">Así lo interpretó el sistema · borrador sin confirmar</h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="border-b-2 border-borde text-xs uppercase tracking-wide text-suave">
                  <th className="px-1.5 py-2">Hora</th>
                  <th className="px-1.5 py-2">Tipo</th>
                  <th className="px-1.5 py-2">Descripción</th>
                  <th className="px-1.5 py-2">Cantidad</th>
                  <th className="px-1.5 py-2">Unidad</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr key={f.id_evento} className="border-b border-borde align-top">
                    <td className="px-1.5 py-2">
                      <input type="time" value={f.hora} onChange={(e) => cambiar(i, { hora: e.target.value, hora_propuesta: false, hora_aproximada: false })} className={`${campo} w-32`} aria-label={`Hora del evento ${i + 1}`} />
                      {f.hora_propuesta && <span className="mt-1 block text-xs text-error">propuesta</span>}
                      {!f.hora_propuesta && f.hora_aproximada && <span className="mt-1 block text-xs text-aviso">aproximada</span>}
                      {f.fecha !== fecha && <span className="mt-1 block text-xs text-suave">{f.fecha.split("-").reverse().join("/")}</span>}
                    </td>
                    <td className="px-1.5 py-2">
                      <select
                        value={f.tipo}
                        onChange={(e) => {
                          const tipo = e.target.value as TipoEvento;
                          cambiar(i, { tipo, unidad: TIPOS[tipo].unidades[0] ?? "", cantidad: TIPOS[tipo].unidades.length ? f.cantidad : "" });
                        }}
                        className={`${campo} min-w-[9.5rem]`}
                        aria-label={`Tipo del evento ${i + 1}`}
                        style={{ background: TIPOS[f.tipo]?.fondo, color: TIPOS[f.tipo]?.texto }}
                      >
                        {(Object.keys(TIPOS) as TipoEvento[]).map((t) => (
                          <option key={t} value={t}>{TIPOS[t].nombre}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-1.5 py-2">
                      <input value={f.descripcion} maxLength={160} onChange={(e) => cambiar(i, { descripcion: e.target.value })} className={campo} aria-label={`Descripción del evento ${i + 1}`} />
                    </td>
                    <td className="px-1.5 py-2">
                      <input value={f.cantidad} inputMode="decimal" disabled={!TIPOS[f.tipo].unidades.length} onChange={(e) => cambiar(i, { cantidad: e.target.value })} className={`${campo} w-16`} aria-label={`Cantidad del evento ${i + 1}`} />
                    </td>
                    <td className="px-1.5 py-2">
                      {TIPOS[f.tipo].unidades.length ? (
                        <select value={f.unidad} onChange={(e) => cambiar(i, { unidad: e.target.value })} className={`${campo} min-w-[7.5rem]`} aria-label={`Unidad del evento ${i + 1}`}>
                          {TIPOS[f.tipo].unidades.map((u) => (
                            <option key={u} value={u}>{u}</option>
                          ))}
                        </select>
                      ) : (
                        <span className="text-suave">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 rounded-lg border border-dashed border-borde bg-fondo p-3 text-sm text-suave">
            {advertencias.map((a) => (
              <p key={a} className="mb-1 text-aviso">{a}</p>
            ))}
            <p>
              Los eventos quedan como borrador y solo se asocian a las mediciones cuando los confirmás. El texto original se
              guarda junto a cada evento.
            </p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={confirmar}
              disabled={estado !== "libre"}
              className="rounded-lg bg-activo-borde px-5 py-2.5 font-semibold text-marca-oscuro hover:brightness-95 disabled:opacity-60"
            >
              {estado === "confirmando" ? "Guardando…" : `Confirmar ${filas.length === 1 ? "el evento" : `los ${filas.length} eventos`}`}
            </button>
            <button type="button" onClick={descartar} className="rounded-lg border border-marca px-5 py-2.5 font-medium text-marca hover:bg-activo">
              Descartar
            </button>
          </div>
        </section>
      )}
    </>
  );
}
