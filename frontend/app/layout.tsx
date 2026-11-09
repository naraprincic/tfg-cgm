import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Glucosa y eventos cotidianos",
  description:
    "Prototipo del Trabajo Final de Grado: integración de mediciones de CGM con eventos cotidianos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
