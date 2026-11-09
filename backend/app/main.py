"""Punto de entrada del backend (la "cocina" de la aplicación)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import models  # noqa: F401  (importarlo registra las tablas)
from app.config import settings
from app.database import Base, crear_base_si_falta, engine
from app.routers import auth, configuracion, dias, eventos, importaciones, mediciones


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar, crea la base (si falta) y las tablas que todavía no existan.
    crear_base_si_falta()
    Base.metadata.create_all(bind=engine)
    # Columnas agregadas después de la primera versión (bases creadas antes no las tienen).
    if engine.dialect.name == "postgresql":
        with engine.begin() as conexion:
            for columna in ("formato_fecha VARCHAR(40)", "zona_horaria VARCHAR(64)"):
                conexion.execute(text(f"ALTER TABLE importacion ADD COLUMN IF NOT EXISTS {columna}"))
    yield


app = FastAPI(
    title="API – CGM y eventos cotidianos",
    description="Backend del prototipo del Trabajo Final de Grado (Princic-Lozza, Nara).",
    version="0.5.0",
    lifespan=lifespan,
)

# Las respuestas de la API tienen datos de salud: ningún intermediario (navegador, CDN) debe guardarlas.
@app.middleware("http")
async def sin_cache(request: Request, siguiente):
    respuesta = await siguiente(request)
    respuesta.headers.setdefault("Cache-Control", "no-store")
    return respuesta


# CORS: por seguridad, el navegador solo deja que el frontend le hable al backend si el backend lo autoriza explícitamente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def errores_de_validacion_en_espanol(request: Request, exc: RequestValidationError):
    """Cuando los datos enviados no cumplen las reglas, FastAPI responde en inglés."""
    errores = []
    for error in exc.errors():
        campo = str(error["loc"][-1]) if len(error["loc"]) > 1 else "general"
        tipo = error["type"]
        if tipo == "missing":
            mensaje = "Este campo es obligatorio."
        elif tipo == "value_error" and error["msg"].startswith("Value error, "):
            # Mensajes escritos por nosotros en schemas.py (ya están en español).
            mensaje = error["msg"].removeprefix("Value error, ")
        elif tipo == "value_error" and campo == "email":
            mensaje = "El correo electrónico no tiene un formato válido."
        else:
            mensaje = "El valor ingresado no es válido."
        errores.append({"campo": campo, "mensaje": mensaje})

    return JSONResponse(
        status_code=422,
        content={"detail": "Revisá los datos ingresados.", "errores": errores},
    )


app.include_router(auth.router)
app.include_router(importaciones.router)
app.include_router(mediciones.router)
app.include_router(dias.router)
app.include_router(eventos.router)
app.include_router(configuracion.router)


@app.get("/ia/estado", tags=["Sistema"])
def estado_ia():
    """Indica si la inteligencia artificial está configurada y qué modelo usa."""
    from app.ia import cliente

    return {"disponible": cliente.disponible(), "modelo": cliente.modelo()}


@app.get("/salud", tags=["Sistema"])
def salud():
    """Verifica que la API esté funcionando y que pueda conectarse a la base de datos."""
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        base_de_datos = "conectada"
    except Exception as error:  # se muestra el motivo para poder diagnosticar
        base_de_datos = f"error: {error.__class__.__name__}: {error}"

    return {"api": "funcionando", "base_de_datos": base_de_datos}
