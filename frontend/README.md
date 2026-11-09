# Frontend – Next.js + React + TypeScript

Interfaz web del prototipo. Ver las instrucciones completas en el `README.md` de la carpeta principal.

```powershell
npm install      # solo la primera vez (o si cambió package.json)
npm run dev      # abre http://localhost:3000
```

El backend tiene que estar corriendo en http://localhost:8000. Todo pedido a `/api/...`
se reenvía al backend (ver `next.config.ts`).

## Estructura

```
app/
├── (publico)/login       inicio de sesión (HU-002)
├── (publico)/registro    registro con consentimiento (HU-001)
├── (app)/layout.tsx      marco con sesión: encabezado, menú, control de sesión (HU-002/003)
├── (app)/inicio          curva de glucosa del día
└── (app)/importar        validación e importación del CSV (HU-005/006)
components/               piezas reutilizables (marco, formularios, gráfico)
lib/api.ts                comunicación con el backend
```
