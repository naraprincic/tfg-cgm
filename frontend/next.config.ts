import type { NextConfig } from "next";

// Dirección del backend (FastAPI).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  // Oculta el botón flotante de Next.js que aparece solo en modo desarrollo.
  devIndicators: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Todo pedido a /api/...
  async rewrites() {
    return [{ source: "/api/:ruta*", destination: `${BACKEND_URL}/:ruta*` }];
  },
};

export default nextConfig;
