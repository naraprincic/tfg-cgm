"use client";

/** Curva de glucosa de un día con la banda del rango objetivo (Chart.js). */

import {
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartOptions,
  type Plugin,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { PERIODOS, TIPOS, nombreTipo, type TipoEvento } from "@/lib/eventos";

ChartJS.register(LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const MARCA = "#1b4d57";
const RANGO = "rgba(155, 203, 122, 0.25)";
const RANGO_BORDE = "rgba(110, 160, 90, 0.7)";

export type PuntoGrafico = { hora: string; valor: number; marca?: string | null };
export type MarcaEvento = { hora: string; tipo: string; descripcion: string };
export type ZonaPeriodo = { desde: string; hasta: string; tipo: string };

function aMinutos(hora: string) {
  const [h, m] = hora.split(":").map(Number);
  return h * 60 + m;
}

function aHora(minutos: number) {
  const h = Math.floor(minutos / 60);
  const m = Math.round(minutos % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export default function GraficoGlucosa({
  puntos,
  rangoMin,
  rangoMax,
  eventos = [],
  periodos = [],
  alto = "h-72 sm:h-80",
}: {
  puntos: PuntoGrafico[];
  rangoMin: number;
  rangoMax: number;
  eventos?: MarcaEvento[];
  periodos?: ZonaPeriodo[];
  alto?: string;
}) {
  const serie = puntos.map((p) => ({ x: aMinutos(p.hora), y: p.valor, marca: p.marca ?? null }));
  const borde = [{ x: 0 }, { x: 1440 }];

  // Dibuja los períodos (fondo) y los eventos (líneas) directamente sobre el gráfico.
  const decoraciones: Plugin<"line"> = {
    id: "decoraciones",
    beforeDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      ctx.save();
      for (const p of periodos) {
        const desde = scales.x.getPixelForValue(aMinutos(p.desde));
        let hastaMin = aMinutos(p.hasta);
        if (hastaMin < aMinutos(p.desde)) hastaMin = 1440; // termina a la medianoche
        const hasta = scales.x.getPixelForValue(hastaMin);
        ctx.fillStyle = PERIODOS[p.tipo]?.color ?? "rgba(0,0,0,0.05)";
        ctx.fillRect(desde, chartArea.top, Math.max(2, hasta - desde), chartArea.bottom - chartArea.top);
      }
      ctx.restore();
    },
    afterDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      for (const e of eventos) {
        const x = scales.x.getPixelForValue(aMinutos(e.hora));
        ctx.strokeStyle = TIPOS[e.tipo as TipoEvento]?.color ?? "#d9534f";
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.stroke();
      }
      ctx.restore();
    },
  };

  const datos = {
    datasets: [
      {
        label: "Glucosa medida por el sensor",
        data: serie,
        borderColor: MARCA,
        backgroundColor: MARCA,
        borderWidth: 2,
        pointRadius: serie.length > 150 ? 0 : 2,
        pointHoverRadius: 4,
        tension: 0.2,
        order: 1,
      },
      {
        label: `Rango objetivo ${rangoMin}–${rangoMax} mg/dL`,
        data: borde.map((p) => ({ ...p, y: rangoMax })),
        borderColor: RANGO_BORDE,
        borderDash: [4, 4],
        borderWidth: 1,
        pointRadius: 0,
        backgroundColor: RANGO,
        fill: "+1", // pinta hasta la línea del límite inferior
        order: 2,
      },
      {
        label: "límite inferior",
        data: borde.map((p) => ({ ...p, y: rangoMin })),
        borderColor: RANGO_BORDE,
        borderDash: [4, 4],
        borderWidth: 1,
        pointRadius: 0,
        order: 3,
      },
    ],
  };

  const opciones: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "nearest", intersect: false, axis: "x" },
    scales: {
      x: {
        type: "linear",
        min: 0,
        max: 1440,
        ticks: { stepSize: 180, callback: (v) => aHora(Number(v)) },
        grid: { color: "#eef1f0" },
      },
      y: {
        min: 40,
        suggestedMax: 260,
        title: { display: true, text: "mg/dL" },
        grid: { color: "#eef1f0" },
      },
    },
    plugins: {
      legend: {
        position: "top",
        align: "start",
        labels: { boxWidth: 14, filter: (item) => item.text !== "límite inferior" },
      },
      tooltip: {
        filter: (item) => item.datasetIndex === 0,
        callbacks: {
          title: (items) => aHora(Number(items[0].parsed.x)),
          label: (item) => {
            const marca = (item.raw as { marca: string | null }).marca;
            const sufijo =
              marca === "bajo" ? " (por debajo del límite del sensor)" : marca === "alto" ? " (por encima del límite del sensor)" : "";
            return ` ${item.parsed.y} mg/dL${sufijo}`;
          },
          afterBody: (items) => {
            const minuto = Number(items[0].parsed.x);
            return eventos
              .filter((e) => Math.abs(aMinutos(e.hora) - minuto) <= 7)
              .map((e) => `${e.hora} · ${nombreTipo(e.tipo)}: ${e.descripcion}`);
          },
        },
      },
    },
  };

  return (
    <div>
      <div className={alto} role="img" aria-label={`Curva de glucosa del día con ${puntos.length} mediciones y ${eventos.length} eventos`}>
        <Line data={datos} options={opciones} plugins={[decoraciones]} />
      </div>
      {(eventos.length > 0 || periodos.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-suave">
          {eventos.length > 0 && <span>Líneas punteadas: eventos registrados.</span>}
          {(Object.keys(TIPOS) as TipoEvento[])
            .filter((tipo) => eventos.some((e) => e.tipo === tipo))
            .map((tipo) => (
              <span key={tipo} className="flex items-center gap-1.5">
                <span className="inline-block h-3 border-l-2 border-dashed" style={{ borderColor: TIPOS[tipo].color }} />
                {TIPOS[tipo].nombre}
              </span>
            ))}
          {periodos.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-4 bg-[rgba(217,83,79,0.15)]" /> Período fuera de rango o de variación
            </span>
          )}
        </div>
      )}
    </div>
  );
}
