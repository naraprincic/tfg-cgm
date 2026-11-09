"""Preparación de las pruebas automáticas."""

import os

# La configuración exige DATABASE_URL; para las pruebas no se usa la real.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    # Misma configuración de sesión que la aplicación (app/database.py).
    sesion = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield sesion
    finally:
        sesion.close()
        engine.dispose()


@pytest.fixture
def cliente(db):
    """Un "navegador de mentira" que le hace pedidos a la API."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
