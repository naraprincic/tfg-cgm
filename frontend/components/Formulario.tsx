/** Piezas reutilizables de los formularios (registro e inicio de sesión). */

export function Tarjeta({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-borde bg-white p-8 shadow-sm sm:p-10">
        <p className="mb-1 text-sm text-suave">Glucosa y eventos cotidianos</p>
        <h1 className="mb-6 text-2xl font-bold text-marca sm:text-3xl">{titulo}</h1>
        {children}
      </div>
    </main>
  );
}

export function Campo({
  id,
  etiqueta,
  error,
  ayuda,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  etiqueta: string;
  error?: string;
  ayuda?: string;
}) {
  const idDescripcion = error ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined;
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1.5 block text-suave">
        {etiqueta}
      </label>
      <input
        id={id}
        name={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={idDescripcion}
        className={`w-full rounded-lg border px-4 py-3 text-base outline-none focus:border-marca ${
          error ? "border-error" : "border-borde"
        }`}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-error">
          {error}
        </p>
      ) : ayuda ? (
        <p id={`${id}-ayuda`} className="mt-1.5 text-sm text-suave">
          {ayuda}
        </p>
      ) : null}
    </div>
  );
}

export function Alerta({ tipo, children }: { tipo: "error" | "ok" | "aviso"; children: React.ReactNode }) {
  const estilos = {
    error: "bg-error-fondo text-error",
    ok: "bg-ok-fondo text-ok",
    aviso: "bg-aviso-fondo text-aviso",
  }[tipo];
  return (
    <div role={tipo === "error" ? "alert" : "status"} className={`mb-4 rounded-lg px-4 py-3 text-sm ${estilos}`}>
      {children}
    </div>
  );
}

export function BotonPrincipal({
  cargando,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { cargando?: boolean }) {
  return (
    <button
      disabled={cargando || props.disabled}
      className="w-full rounded-lg bg-marca px-4 py-3 text-base font-medium text-white hover:bg-marca-oscuro disabled:opacity-60"
      {...props}
    >
      {cargando ? "Un momento…" : children}
    </button>
  );
}
