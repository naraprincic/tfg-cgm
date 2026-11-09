# Aplicación Web para Relacionar Mediciones de CGM con Eventos Cotidianos

Prototipo del Trabajo Final de Grado – Licenciatura en Informática, Universidad Siglo 21.
Autora: Princic-Lozza, Nara.

## Probarlo rápido

- **Demo en línea:** https://tfg-cgm.vercel.app — en la pantalla de inicio de sesión, tocar «Completar con la cuenta de prueba» e «Ingresar». La cuenta ya tiene 38 días de mediciones sintéticas, eventos y resúmenes cargados. El servidor gratuito se suspende tras unos minutos sin uso: el primer ingreso puede tardar alrededor de un minuto.
- **En la compu (Windows):** con Python 3.14, Node.js y PostgreSQL instalados, doble clic en `iniciar.bat`.
  La primera vez instala todo y pide la contraseña de PostgreSQL; la base de datos se crea sola.
  Después, `cargar_demo.bat` crea la cuenta de prueba con datos sintéticos.

## Estructura

```
tesis-cgm/
├── backend/          API en Python con FastAPI
│   ├── app/
│   │   ├── main.py           punto de entrada, rutas y mensajes de error en español
│   │   ├── config.py         configuración (lee el archivo .env)
│   │   ├── database.py       conexión con PostgreSQL
│   │   ├── models.py         tablas: usuario, configuracion, sesion, control_acceso, importacion,
│   │   │                     medicion, indicador_diario, periodo_relevante, evento, resumen_diario
│   │   ├── schemas.py        reglas de validación de los datos de registro e inicio de sesión
│   │   ├── seguridad.py      hash de contraseñas (bcrypt, costo 12)
│   │   ├── sesiones.py       sesiones con cookie HttpOnly y cierre por inactividad
│   │   ├── importacion/
│   │   │   ├── adaptadores.py   lectura de LibreView, Dexcom Clarity y genérico (Anexo I)
│   │   │   └── validacion.py    validación y normalización con Pandas (HU-006)
│   │   ├── ia/
│   │   │   ├── cliente.py       conexión con la API de OpenAI (salidas JSON con esquema)
│   │   │   ├── extraccion.py    eventos en lenguaje natural -> borradores (HU-008)
│   │   │   └── resumen.py       resumen diario, verificación automática y plantilla (HU-013)
│   │   ├── analisis/
│   │   │   ├── indicadores.py   indicadores ponderados por tiempo y períodos relevantes (HU-007, 011)
│   │   │   ├── asociacion.py    ventanas temporales entre eventos y mediciones (HU-010)
│   │   │   └── servicio.py      recálculo y guardado de los indicadores diarios
│   │   └── routers/
│   │       ├── auth.py          registro, inicio y cierre de sesión (HU-001, 002, 003)
│   │       ├── importaciones.py validación e importación de archivos (HU-005, 006)
│   │       ├── configuracion.py rango objetivo y zona horaria (HU-004)
│   │       ├── eventos.py       eventos: lenguaje natural y carga manual (HU-008, 009)
│   │       ├── dias.py          detalle del día, resumen e historial (HU-010, 012, 013, 014)
│   │       └── mediciones.py    consulta de mediciones por día
│   ├── tests/        pruebas automáticas (pytest)
│   └── requirements.txt
├── frontend/         interfaz en Next.js + React + TypeScript (ver frontend/README.md)
└── datos_prueba/     archivos CSV sintéticos generados con simglucose (ver LEEME.md)
```

## Primera vez en cada computadora

Requisitos: Python 3.14, Node.js LTS y PostgreSQL instalados.

**1. Base de datos.** En pgAdmin: *Servers → PostgreSQL → Databases* → clic derecho →
*Create → Database…* → nombre `tesis_cgm` → *Save*.

**2. Backend.** En una terminal (en VS Code: *Terminal → New Terminal*):
```powershell
cd C:\tesis-cgm\backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```
En el Bloc de notas, reemplazar `TU_CONTRASEÑA` por la contraseña de PostgreSQL y guardar.

*Opcional – inteligencia artificial:* en el mismo archivo, pegar la clave de la API de OpenAI
después de `OPENAI_API_KEY=` (sin espacios ni comillas). Sin clave, la aplicación funciona igual:
los eventos se cargan manualmente y el resumen diario se genera con una plantilla automática.
La clave nunca se sube a GitHub (el archivo `.env` está excluido).

**3. Frontend.** En una **segunda** terminal (botón **+** del panel de terminales):
```powershell
cd C:\tesis-cgm\frontend
npm install
```

## Cada vez que se trabaja

Se necesitan **dos terminales abiertas a la vez**, una para cada parte.

Terminal 1 – backend:
```powershell
cd C:\tesis-cgm\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Terminal 2 – frontend:
```powershell
cd C:\tesis-cgm\frontend
npm run dev
```

Abrir **http://localhost:3000** en el navegador.
La documentación de la API está en http://localhost:8000/docs.
Para detener cada servidor: `Ctrl + C` en su terminal.

Si cambió `requirements.txt` → `pip install -r requirements.txt` (con el entorno activado).
Si cambió `package.json` → `npm install` (en la carpeta frontend).

## Pruebas automáticas

```powershell
cd C:\tesis-cgm\backend
.\.venv\Scripts\Activate.ps1
pytest
```
Usan una base temporal en memoria: no modifican la base de datos real.

## Avance del prototipo

Las 14 historias del product backlog están implementadas (114 de 114 puntos).

| Historia | Estado |
|---|---|
| HU-001 Registro del usuario, con consentimiento (Ley 25.326, art. 5) | Hecha |
| HU-002 Inicio de sesión (cierre por 30 min de inactividad, bloqueo tras 5 intentos) | Hecha |
| HU-003 Cierre de sesión con revocación del token | Hecha |
| HU-004 Configuración del rango objetivo (recalcula los días) | Hecha |
| HU-005 Importación de las mediciones | Hecha |
| HU-006 Validación del archivo (LibreView, Dexcom Clarity, genérico) | Hecha |
| HU-007 Indicadores diarios ponderados por tiempo, cobertura y GMI | Hecha |
| HU-008 Registro de eventos en lenguaje natural con IA (borradores a confirmar) | Hecha |
| HU-009 Carga manual de eventos | Hecha |
| HU-010 Asociación temporal entre eventos y mediciones | Hecha |
| HU-011 Detección de períodos relevantes | Hecha |
| HU-012 Detalle del día | Hecha |
| HU-013 Resumen diario con IA, verificación automática, plantilla y versiones | Hecha |
| HU-014 Historial de días procesados | Hecha |

Pendiente (apartado Seguridad, etapas siguientes): verificación del correo por enlace, aviso por
correo ante bloqueo, recuperación de contraseña, seguridad a nivel de fila de PostgreSQL y el perfil
de cuidador. Pendiente de evaluación: corpus de 100 descripciones del Anexo II con la clave real.
