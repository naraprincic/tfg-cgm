"""Conexión con la base de datos PostgreSQL (la "heladera")."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# El "engine" es el que sabe cómo llegar a la base de datos.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Cada pedido que llega a la API abre una "sesión" (una conversación con la base) y la cierra al terminar.
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def crear_base_si_falta() -> None:
    """Si la base de PostgreSQL todavía no existe (primera vez en una compu nueva), la crea."""
    url = make_url(settings.database_url)
    if not url.drivername.startswith("postgresql"):
        return
    try:
        with engine.connect():
            return
    except OperationalError as error:
        if "does not exist" not in str(error) and "no existe" not in str(error):
            raise  # otro problema (por ejemplo, la contraseña): que se vea el error real
    maestro = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with maestro.connect() as conexion:
        conexion.execute(text(f'CREATE DATABASE "{url.database}"'))
    maestro.dispose()


class Base(DeclarativeBase):
    """Clase madre de todos los modelos (Usuario, Medicion, Evento, ...)."""


def get_db():
    """Entrega una sesión de base de datos a cada endpoint y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
