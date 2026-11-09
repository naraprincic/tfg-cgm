/** Semáforo del día: en qué horarios la glucosa estuvo en el rango personal (verde), por encima (amarillo) o por debajo (rojo), y qué eventos se registraron en esos horarios. */

import { EtiquetaTipo } from "@/components/Eventos";
import type { Horario, Semaforo as DatosSemaforo } from "@/lib/api";
import { cantidadTexto } from "@/lib/eventos";

const COLORES = {
  verde: { borde: "border-ok/40", fondo: "bg-ok-fondo", punto: "bg-ok", titulo: "text-ok" },
  amarillo: { borde: "border-[#e0b030]/50", fondo: "bg-aviso-fondo", punto: "bg-[#e0a800]", titulo: "text-aviso" },
  rojo: { borde: "border-error/40", fondo: "bg-error-fondo", punto: "bg-error", titulo: "text-error" },
};

function Recuadro({
  color,
  titulo,
  subtitulo,
  children,
}: {
  color: keyof typeof COLORES;
  titulo: string;
  subtitulo: string;
  children: React.ReactNode;
}) {
  const c = COLORES[color];
  return (
    <div className={`rounded-xl border ${c.borde} ${c.fondo} p-4`}>
      <h3 className={`flex items-center gap-2 font-semibold ${c.titulo}`}>
        <span aria-hidden className={`h-3 w-3 shrink-0 rounded-full ${c.punto}`} />
        {titulo}
      </h3>
      <p className="mb-3 text-sm text-suave">{subtitulo}</p>
      {children}
    </div>
  );
}

function HorarioFuera({ h, valor, horasPrevias }: { h: Horario; valor: string; horasPrevias: number }) {
  return (
    <li className="rounded-lg bg-white/70 px-3 py-2.5">
      <p className="font-semibold">
        {h.desde} a {h.hasta} <span className="font-normal text-suave">({h.cuando})</span>
      </p>
      <p className="text-sm">
        Durante {h.duracion}. {valor}: {h.valor_extremo} mg/dL.
      </p>
      {h.eventos.length === 0 ? (
        <p className="mt-1 text-sm text-suave">
          No registraste eventos en ese horario ni en las {horasPrevias} horas previas.
        </p>
      ) : (
        <>
          <p className="mt-1.5 text-sm text-suave">En ese horario o en las {horasPrevias} horas previas registraste:</p>
          <ul className="mt-1 space-y-1">
            {h.eventos.map((e) => (
              <li key={`${e.hora}-${e.descripcion}`} className="grid grid-cols-[2.75rem_1fr] gap-x-1 text-sm">
                <span className="pt-0.5 font-medium">{e.hora}</span>
                <span>
                  <EtiquetaTipo tipo={e.tipo} />{" "}
                  {e.descripcion}
                  {e.cantidad != null && ` — ${cantidadTexto(e.cantidad, e.unidad)}`}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </li>
  );
}

const minutos = (h: string) => Number(h.slice(0, 2)) * 60 + Number(h.slice(3, 5));

/** Línea horizontal de 0 a 24 h pintada con los colores del semáforo. */
function BarraDelDia({ s }: { s: DatosSemaforo }) {
  const tramos = [
    ...s.en_rango.horarios.map((h) => ({ h, clase: "bg-ok", texto: "en tu rango" })),
    ...s.alto.map((h) => ({ h, clase: "bg-[#e0a800]", texto: "por encima de tu rango" })),
    ...s.bajo.map((h) => ({ h, clase: "bg-error", texto: "por debajo de tu rango" })),
  ];
  return (
    <div>
      <div className="relative h-7 overflow-hidden rounded-lg bg-borde" role="img"
        aria-label={tramos
          .sort((a, b) => a.h.desde.localeCompare(b.h.desde))
          .map((t) => `de ${t.h.desde} a ${t.h.hasta} ${t.texto}`)
          .join("; ")}
      >
        {tramos.map((t) => (
          <div
            key={`${t.clase}-${t.h.desde}`}
            title={`${t.h.desde} a ${t.h.hasta}: ${t.texto}`}
            className={`absolute inset-y-0 ${t.clase}`}
            style={{
              left: `${(minutos(t.h.desde) / 1440) * 100}%`,
              width: `${Math.max(((minutos(t.h.hasta) - minutos(t.h.desde)) / 1440) * 100, 0.4)}%`,
            }}
          />
        ))}
      </div>
      <div className="relative mt-1 h-4 text-xs text-suave">
        {[0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => (
          <span
            key={h}
            className={`absolute ${h === 0 ? "" : h === 24 ? "-translate-x-full" : "-translate-x-1/2"} ${h % 6 ? "hidden sm:inline" : ""}`}
            style={{ left: `${(h / 24) * 100}%` }}
          >
            {String(h).padStart(2, "0")}:00
          </span>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-suave">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-ok" />En tu rango</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-[#e0a800]" />Por encima</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-error" />Por debajo</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-borde" />Sin datos o cambios de menos de 15 minutos</span>
      </div>
    </div>
  );
}

export default function Semaforo({ s }: { s: DatosSemaforo }) {
  const rango = `${s.rango_min} a ${s.rango_max} mg/dL`;
  return (
    <details className="group mt-5 rounded-xl border border-borde bg-white p-5">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <div className="mb-1 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-marca">Tu día en colores</h2>
          <span className="flex shrink-0 items-center gap-1 text-sm font-medium text-marca">
            <span className="group-open:hidden">Ver horarios</span>
            <span className="hidden group-open:inline">Ocultar horarios</span>
            <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="transition-transform group-open:rotate-180">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </span>
        </div>
        <p className="mb-4 text-sm text-suave">
          En qué horarios tu glucosa estuvo dentro, por encima o por debajo de tu rango ({rango}).
        </p>
        <BarraDelDia s={s} />
      </summary>
      <div className="mt-5 grid gap-4">
        <Recuadro color="verde" titulo="En tu rango" subtitulo={`${s.en_rango.tiempo} (${s.en_rango.porcentaje} % del tiempo con datos)`}>
          {s.en_rango.horarios.length === 0 ? (
            <p className="text-sm text-suave">No hubo tramos largos dentro de tu rango.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {s.en_rango.horarios.map((h) => (
                <li key={h.desde} className="rounded-lg bg-white/70 px-3 py-2 text-sm">
                  <span className="font-semibold">
                    {h.desde} a {h.hasta}
                  </span>{" "}
                  <span className="text-suave">({h.duracion})</span>
                </li>
              ))}
            </ul>
          )}
        </Recuadro>

        <Recuadro
          color="amarillo"
          titulo="Por encima de tu rango"
          subtitulo={s.alto.length ? `${s.alto.length} ${s.alto.length === 1 ? "momento" : "momentos"} de 15 minutos o más` : `Más de ${s.rango_max} mg/dL`}
        >
          {s.alto.length === 0 ? (
            <p className="text-sm">No estuvo por encima de tu rango durante 15 minutos o más.</p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {s.alto.map((h) => (
                <HorarioFuera key={h.desde} h={h} valor="Valor más alto" horasPrevias={s.horas_previas} />
              ))}
            </ul>
          )}
        </Recuadro>

        <Recuadro
          color="rojo"
          titulo="Por debajo de tu rango"
          subtitulo={s.bajo.length ? `${s.bajo.length} ${s.bajo.length === 1 ? "momento" : "momentos"} de 15 minutos o más` : `Menos de ${s.rango_min} mg/dL`}
        >
          {s.bajo.length === 0 ? (
            <p className="text-sm">No estuvo por debajo de tu rango durante 15 minutos o más.</p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {s.bajo.map((h) => (
                <HorarioFuera key={h.desde} h={h} valor="Valor más bajo" horasPrevias={s.horas_previas} />
              ))}
            </ul>
          )}
        </Recuadro>
      </div>
      <p className="mt-3 text-xs text-suave">
        Los eventos se muestran porque coinciden en el horario; eso no significa que hayan causado esos valores.
      </p>
    </details>
  );
}
