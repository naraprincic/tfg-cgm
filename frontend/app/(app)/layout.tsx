import MarcoAplicacion from "@/components/MarcoAplicacion";

// Todas las pantallas dentro de (app) requieren sesión iniciada.

export default function LayoutPrivado({ children }: { children: React.ReactNode }) {
  return <MarcoAplicacion>{children}</MarcoAplicacion>;
}
