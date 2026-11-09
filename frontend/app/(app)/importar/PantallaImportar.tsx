"use client";

/** Importación de mediciones (HU-005 y HU-006) – Figura 7 de la tesis. */

import { useCallback, useEffect, useRef, useState } from "react";
import { Alerta } from "@/components/Formulario";
import { useManejarSesionVencida } from "@/components/MarcoAplicacion";
import { api, type Importacion, type ResumenValidacion } from "@/lib/api";

const formatoFecha = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});
const formatoDia = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "2-digit" });
const numero = new Intl.NumberFormat("es-AR");

export default function PaginaImportar() {
  const manejarSesion = useManejarSesionVencida();
  const entrada = useRef<HTMLInputElement>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  // Formato regional de fecha confirmado por la persona (LibreView: día-mes o mes-día).
  const [varianteFecha, setVarianteFecha] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResumenValidacion | null>(null);
  const [importado, setImportado] = useState<ResumenValidacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState<"validando" | "importando" | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [historial, setHistorial] = useState<Importacion[] | null>(null);

  const cargarHistorial = useCallback(
    () =>
      api<Importacion[]>("/importaciones")
        .then(setHistorial)
        .catch((e) => {
          if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
        }),
    [manejarSesion],
  );

  useEffect(() => {
    cargarHistorial();
  }, [cargarHistorial]);

  async function validar(elegido: File, formato: string | null = null) {
    setArchivo(elegido);
    setVarianteFecha(formato);
    setResultado(null);
    setImportado(null);
    setError(null);
    setCargando("validando");
    const datos = new FormData();
    datos.append("archivo", elegido);
    if (formato) datos.append("formato_fecha", formato);
    try {
      setResultado(await api<ResumenValidacion>("/importaciones/validar", { method: "POST", body: datos }));
      cargarHistorial(); // los rechazos también quedan en el listado
    } catch (e) {
      if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
    } finally {
      setCargando(null);
      if (entrada.current) entrada.current.value = "";
    }
  }

  async function confirmar() {
    if (!archivo) return;
    setError(null);
    setCargando("importando");
    const datos = new FormData();
    datos.append("archivo", archivo);
    if (varianteFecha) datos.append("formato_fecha", varianteFecha);
    try {
      setImportado(await api<ResumenValidacion>("/importaciones", { method: "POST", body: datos }));
      setResultado(null);
      setArchivo(null);
      cargarHistorial();
    } catch (e) {
      if (!manejarSesion(e)) setError(e instanceof Error ? e.message : "Error inesperado.");
    } finally {
      setCargando(null);
    }
  }

  function alSoltar(e: React.DragEvent) {
    e.preventDefault();
    setArrastrando(false);
    const elegido = e.dataTransfer.files?.[0];
    if (elegido) validar(elegido);
  }

  return (
    <div className="mx-auto max-w-5xl">
      <p className="mb-4 text-suave">
        Carga del archivo exportado por la aplicación del sistema de monitoreo continuo de glucosa
      </p>

      {/* Zona de carga */}
      <section
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={alSoltar}
        className={`mb-5 rounded-xl border-2 border-dashed bg-white px-6 py-8 text-center transition ${
          arrastrando ? "border-marca bg-activo" : "border-borde"
        }`}
      >
        <p className="text-lg font-semibold sm:text-xl">
          Arrastrá aquí el archivo CSV exportado por la aplicación de tu sensor
        </p>
        <p className="mb-4 mt-1 text-suave">o seleccionalo desde tu dispositivo · formato .csv · hasta 10 MB</p>
        <input
          ref={entrada}
          id="archivo"
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(e) => e.target.files?.[0] && validar(e.target.files[0])}
        />
        <label
          htmlFor="archivo"
          className="inline-block cursor-pointer rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro"
        >
          {cargando === "validando" ? "Validando…" : "Seleccionar archivo"}
        </label>
      </section>

      <div aria-live="polite">
        {error && <Alerta tipo="error">{error}</Alerta>}
        {resultado?.requiere_formato_fecha && archivo ? (
          <ElegirFormatoFecha resultado={resultado} onElegir={(f) => validar(archivo, f)} validando={cargando === "validando"} />
        ) : (
          resultado && <ResultadoValidacion resultado={resultado} onConfirmar={confirmar} importando={cargando === "importando"} />
        )}
        {importado && <ResultadoImportacion resultado={importado} />}
      </div>

      {/* Requisitos */}
      <section className="mb-5 rounded-xl border border-borde bg-white p-5">
        <h2 className="mb-2 text-lg font-semibold text-marca">Requisitos del archivo</h2>
        <p className="text-suave">
          Se admiten las exportaciones de LibreView (FreeStyle Libre) y Dexcom Clarity, y un formato genérico
          con las columnas <b className="text-texto">fecha_hora</b> y <b className="text-texto">glucosa_mg_dl</b>.
          El archivo se valida antes de guardar: si más del 20 % de las filas de glucosa son inválidas, se
          rechaza completo y no se almacena ninguna medición. Los duplicados se descartan y se informan aparte.
        </p>
      </section>

      {/* Importaciones anteriores */}
      <section className="rounded-xl border border-borde bg-white p-5">
        <h2 className="mb-3 text-lg font-semibold text-marca">Importaciones anteriores</h2>
        {historial === null ? (
          <p className="text-suave">Cargando…</p>
        ) : historial.length === 0 ? (
          <p className="text-suave">Todavía no importaste ningún archivo.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b-2 border-borde text-xs uppercase tracking-wide text-suave">
                  <th className="px-2 py-2">Archivo</th>
                  <th className="px-2 py-2">Fecha de carga</th>
                  <th className="px-2 py-2">Formato</th>
                  <th className="px-2 py-2">Período</th>
                  <th className="px-2 py-2 text-right">Válidas</th>
                  <th className="px-2 py-2">Descartadas</th>
                  <th className="px-2 py-2">Estado</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((i) => {
                  const descartadas = i.filas_invalidas + i.filas_duplicadas + i.filas_en_conflicto;
                  return (
                    <tr key={i.id_importacion} className="border-b border-borde align-top">
                      <td className="max-w-[12rem] truncate px-2 py-3" title={i.nombre_archivo}>
                        {i.nombre_archivo}
                      </td>
                      <td className="px-2 py-3">{formatoFecha.format(new Date(i.fecha_importacion))}</td>
                      <td className="px-2 py-3">
                        {i.formato ?? "No reconocido"}
                        {i.formato_fecha === "dia-mes" && <span className="block text-xs text-suave">fechas día-mes</span>}
                        {i.formato_fecha === "mes-dia" && <span className="block text-xs text-suave">fechas mes-día</span>}
                      </td>
                      <td className="px-2 py-3">
                        {i.periodo_desde && i.periodo_hasta
                          ? `${formatoDia.format(new Date(i.periodo_desde))} – ${formatoDia.format(new Date(i.periodo_hasta))}`
                          : "—"}
                      </td>
                      <td className="px-2 py-3 text-right">{numero.format(i.mediciones_incorporadas)}</td>
                      <td className="px-2 py-3">
                        {i.estado === "rechazada" && descartadas === 0
                          ? "—"
                          : descartadas === 0
                            ? "0"
                            : `${numero.format(descartadas)} (${i.filas_duplicadas} dup., ${i.filas_invalidas} inv., ${i.filas_en_conflicto} conf.)`}
                      </td>
                      <td className="px-2 py-3">
                        {i.estado === "completada" ? (
                          <span className="rounded-full bg-ok-fondo px-2.5 py-1 text-xs font-semibold text-ok">
                            Procesado
                          </span>
                        ) : (
                          <div className="max-w-[16rem]">
                            <span className="rounded-full bg-error-fondo px-2.5 py-1 text-xs font-semibold text-error">
                              Rechazado
                            </span>
                            {i.motivo_rechazo && <p className="mt-1.5 text-xs text-suave">{i.motivo_rechazo}</p>}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Cifra({ etiqueta, valor, tono }: { etiqueta: string; valor: number | string; tono?: "error" | "aviso" }) {
  const color = tono === "error" ? "text-error" : tono === "aviso" ? "text-aviso" : "text-marca";
  return (
    <div className="rounded-lg border border-borde px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-suave">{etiqueta}</p>
      <p className={`text-2xl font-bold ${color}`}>{typeof valor === "number" ? numero.format(valor) : valor}</p>
    </div>
  );
}

function ListaDetalle({ titulo, filas }: { titulo: string; filas: { fila: number; motivo: string }[] }) {
  if (!filas.length) return null;
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-marca">{titulo} ({filas.length}{filas.length === 50 ? "+" : ""})</summary>
      <ul className="mt-2 max-h-48 overflow-y-auto rounded-lg bg-fondo p-3">
        {filas.map((d) => (
          <li key={`${d.fila}-${d.motivo}`}>
            Fila {d.fila}: {d.motivo}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ElegirFormatoFecha({
  resultado: r,
  onElegir,
  validando,
}: {
  resultado: ResumenValidacion;
  onElegir: (formato: string) => void;
  validando: boolean;
}) {
  const [elegido, setElegido] = useState<string | null>(null);
  return (
    <section className="mb-5 rounded-xl border border-aviso/40 bg-white p-5">
      <h2 className="mb-1 text-lg font-semibold text-marca">Confirmá el formato de las fechas</h2>
      <p className="mb-1 text-sm text-suave">{r.nombre_archivo} · {r.formato}</p>
      <p className="mb-4">
        {r.motivo_rechazo} Por ejemplo, «09-10-2026» puede ser 9 de octubre o 10 de septiembre según la configuración
        regional de la aplicación que lo exportó. Elegí cómo leer la primera fecha del archivo:
      </p>
      <fieldset className="mb-4 space-y-2">
        <legend className="sr-only">Formato de fecha</legend>
        {r.opciones_formato_fecha.map((o) => (
          <label
            key={o.id}
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${elegido === o.id ? "border-marca bg-activo" : "border-borde"}`}
          >
            <input type="radio" name="formato_fecha" value={o.id} checked={elegido === o.id} onChange={() => setElegido(o.id)} className="mt-1 accent-marca" />
            <span>
              <span className="block font-medium">{o.nombre}</span>
              <span className="block text-sm text-suave">{o.ejemplo}</span>
              <span className="block text-xs text-suave">
                {o.filas_legibles} de {o.total} fechas del archivo se pueden leer con este formato
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <button
        type="button"
        disabled={!elegido || validando}
        onClick={() => elegido && onElegir(elegido)}
        className="rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro disabled:opacity-50"
      >
        {validando ? "Validando…" : "Validar con este formato"}
      </button>
    </section>
  );
}

function ResultadoValidacion({
  resultado: r,
  onConfirmar,
  importando,
}: {
  resultado: ResumenValidacion;
  onConfirmar: () => void;
  importando: boolean;
}) {
  if (!r.aceptado) {
    return (
      <section className="mb-5 rounded-xl border border-error/30 bg-white p-5">
        <h2 className="mb-1 text-lg font-semibold text-error">Archivo rechazado</h2>
        <p className="mb-1 text-sm text-suave">{r.nombre_archivo}{r.formato ? ` · ${r.formato}` : ""}</p>
        <p>{r.motivo_rechazo}</p>
        <ListaDetalle titulo="Ver filas inválidas" filas={r.detalle_invalidas} />
      </section>
    );
  }
  return (
    <section className="mb-5 rounded-xl border border-borde bg-white p-5">
      <h2 className="mb-1 text-lg font-semibold text-marca">Archivo validado: listo para importar</h2>
      <p className="mb-4 text-sm text-suave">
        {r.nombre_archivo} · {r.formato}
        {r.desde && r.hasta ? ` · del ${r.desde} al ${r.hasta}` : ""}
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Cifra etiqueta="Mediciones nuevas" valor={r.mediciones_nuevas} />
        <Cifra etiqueta="Días" valor={r.dias} />
        <Cifra etiqueta="Inválidas" valor={r.filas_invalidas} tono={r.filas_invalidas ? "error" : undefined} />
        <Cifra etiqueta="Duplicadas" valor={r.filas_duplicadas} />
        <Cifra etiqueta="En conflicto" valor={r.filas_en_conflicto} tono={r.filas_en_conflicto ? "aviso" : undefined} />
      </div>
      <ListaDetalle titulo="Ver filas inválidas" filas={r.detalle_invalidas} />
      <ListaDetalle titulo="Ver conflictos" filas={r.detalle_conflictos} />
      {r.mediciones_nuevas === 0 ? (
        <p className="mt-4 text-suave">Todas las mediciones de este archivo ya estaban guardadas: no hay nada nuevo para importar.</p>
      ) : (
        <button
          type="button"
          onClick={onConfirmar}
          disabled={importando}
          className="mt-5 rounded-lg bg-marca px-5 py-2.5 font-medium text-white hover:bg-marca-oscuro disabled:opacity-60"
        >
          {importando ? "Importando…" : `Confirmar importación de ${numero.format(r.mediciones_nuevas)} mediciones`}
        </button>
      )}
    </section>
  );
}

function ResultadoImportacion({ resultado: r }: { resultado: ResumenValidacion }) {
  return (
    <Alerta tipo="ok">
      <b>Importación completada.</b> Se incorporaron {numero.format(r.mediciones_nuevas)} mediciones de{" "}
      {r.dias} {r.dias === 1 ? "día" : "días"}. Filas inválidas: {r.filas_invalidas} · duplicadas:{" "}
      {r.filas_duplicadas} · en conflicto: {r.filas_en_conflicto}.
    </Alerta>
  );
}
