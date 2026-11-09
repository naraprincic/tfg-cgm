/** Funciones para hablar con el backend (FastAPI). */

export type ErrorDeCampo = { campo: string; mensaje: string };

export class ErrorApi extends Error {
  estado: number;
  errores: ErrorDeCampo[];

  constructor(estado: number, mensaje: string, errores: ErrorDeCampo[] = []) {
    super(mensaje);
    this.estado = estado;
    this.errores = errores;
  }
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const esFormulario = opciones.body instanceof FormData;
  let respuesta: Response;
  try {
    respuesta = await fetch(`/api${ruta}`, {
      ...opciones,
      credentials: "include",
      cache: "no-store",
      headers: esFormulario
        ? opciones.headers
        : { "Content-Type": "application/json", ...opciones.headers },
    });
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el servidor. ¿Está funcionando el backend?");
  }

  if (respuesta.status === 204) return undefined as T;

  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    const mensaje =
      typeof datos?.detail === "string" ? datos.detail : "Ocurrió un error inesperado.";
    throw new ErrorApi(respuesta.status, mensaje, datos?.errores ?? []);
  }
  return datos as T;
}

// --- Tipos de datos que devuelve el backend --------------------------------

export type Usuario = {
  id_usuario: number;
  email: string;
  rango_min: number;
  rango_max: number;
  zona_horaria: string;
};

export type Detalle = { fila: number; motivo: string };

export type ResumenValidacion = {
  nombre_archivo: string;
  formato: string | null;
  aceptado: boolean;
  motivo_rechazo: string | null;
  filas_glucosa: number;
  filas_invalidas: number;
  filas_duplicadas: number;
  filas_en_conflicto: number;
  mediciones_nuevas: number;
  dias: number;
  desde: string | null;
  hasta: string | null;
  detalle_invalidas: Detalle[];
  detalle_conflictos: Detalle[];
  id_importacion: number | null;
  formato_fecha: string | null;
  zona_horaria: string | null;
  requiere_formato_fecha: boolean;
  opciones_formato_fecha: { id: string; nombre: string; ejemplo: string; filas_legibles: number; total: number }[];
};

export type Importacion = {
  id_importacion: number;
  nombre_archivo: string;
  formato: string | null;
  fecha_importacion: string;
  estado: "completada" | "rechazada";
  motivo_rechazo: string | null;
  mediciones_incorporadas: number;
  filas_invalidas: number;
  filas_duplicadas: number;
  filas_en_conflicto: number;
  dias: number;
  formato_fecha: string | null;
  zona_horaria: string | null;
  periodo_desde: string | null;
  periodo_hasta: string | null;
};

export type DiaConMediciones = {
  fecha: string; // AAAA-MM-DD
  cantidad: number;
  minimo: number;
  maximo: number;
  promedio: number;
};

export type Punto = {
  hora: string; // HH:MM
  fecha_hora: string;
  valor: number;
  marca: "bajo" | "alto" | null;
};

export type Indicadores = {
  fecha: string;
  rango_min: number;
  rango_max: number;
  tir: number;
  tir_personal: number;
  tbr: number;
  tbr_nivel2: number;
  tar: number;
  tar_nivel2: number;
  glucosa_promedio: number;
  coeficiente_variacion: number;
  cobertura: number;
  parcial: boolean;
  mediciones_validas: number;
  tiene_resumen: boolean;
  estado_resumen: "aprobado" | "plantilla" | "desactualizado" | null;
};

export type Historial = {
  desde: string | null;
  hasta: string | null;
  dias: Indicadores[];
  gmi: number | null;
  gmi_detalle: string;
};

export type ValorHora = { valor: number; hora: string };

export type Evento = {
  id_evento: number;
  tipo: string;
  descripcion: string;
  fecha_hora: string;
  fecha: string;
  hora: string;
  hora_aproximada: boolean;
  cantidad: number | null;
  unidad: string | null;
  texto_original: string | null;
};

export type EventoAsociado = Evento & {
  asociacion: {
    ventana: string;
    mediciones_en_ventana: number;
    sin_mediciones: boolean;
    valor_previo: ValorHora | null;
    maximo_posterior: ValorHora | null;
    valor_al_finalizar: ValorHora | null;
    minimo_posterior: ValorHora | null;
    variacion_2h: number | null;
    minimo_ventana: ValorHora | null;
    maximo_ventana: ValorHora | null;
  };
};

export type PeriodoRelevante = {
  tipo: string;
  desde: string;
  hasta: string;
  duracion_min: number;
  valor_extremo: number;
  valor_inicio: number | null;
  valor_fin: number | null;
};

export type DetalleDia = {
  fecha: string;
  rango_min: number;
  rango_max: number;
  indicadores: Indicadores | null;
  periodos: PeriodoRelevante[];
  puntos: { hora: string; valor: number; marca: string | null }[];
  eventos: EventoAsociado[];
  dia_anterior: string | null;
  dia_siguiente: string | null;
  resumen: Resumen | null;
  semaforo: Semaforo | null;
};

export type EventoEnHorario = {
  hora: string;
  tipo: string;
  descripcion: string;
  cantidad: number | null;
  unidad: string | null;
  momento: "antes" | "durante";
};

export type Horario = {
  desde: string;
  hasta: string;
  cuando: string;
  duracion: string;
  valor_extremo: number | null;
  eventos: EventoEnHorario[];
};

export type Semaforo = {
  rango_min: number;
  rango_max: number;
  horas_previas: number;
  en_rango: { porcentaje: number; tiempo: string; horarios: Horario[] };
  alto: Horario[];
  bajo: Horario[];
};

export type Configuracion = { rango_min: number; rango_max: number; zona_horaria: string };

export type Borrador = Evento & { hora_propuesta: boolean; advertencias: string[] };
export type Interpretacion = { texto_original: string; modelo: string; borradores: Borrador[] };
export type EstadoIA = { disponible: boolean; modelo: string };

export type Resumen = {
  fecha: string;
  version: number;
  vigente: boolean;
  texto: string;
  estado_verificacion: "aprobado" | "plantilla" | "desactualizado";
  motivo_generacion: string;
  fecha_generacion: string;
  modelo_utilizado: string;
  observaciones: string[];
  aviso: string;
};
