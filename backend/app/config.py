"""Configuración de la aplicación."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Dirección de conexión a PostgreSQL.
    database_url: str

    # Direcciones desde las que el frontend puede llamar a la API.
    frontend_origins: list[str] = ["http://localhost:3000"]

    # Sesiones (apartado Seguridad): cierre automático por inactividad.
    minutos_inactividad: int = 30
    # En la nube (HTTPS) debe ser true: la cookie de sesión solo viaja cifrada.
    cookie_segura: bool = False

    # Seguridad: bloqueo tras intentos fallidos consecutivos.
    max_intentos_fallidos: int = 5
    minutos_bloqueo: int = 15

    # Inteligencia artificial (HU-008 y HU-013).
    openai_api_key: str | None = None
    # Versión fija del modelo, para que las actualizaciones del proveedor no cambien los resultados.
    modelo_ia: str = "gpt-4o-2024-08-06"

    # Demo pública: tope de pedidos diarios al modelo, para cuidar el saldo de la cuenta de OpenAI.
    limite_ia_diario: int | None = None

    @field_validator("database_url")
    @classmethod
    def usar_psycopg(cls, valor: str) -> str:
        # Los proveedores en la nube (Neon, Render) entregan direcciones "postgres://" o "postgresql://"; SQLAlchemy necesita que se indique el driver psycopg.
        for prefijo in ("postgres://", "postgresql://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg://" + valor[len(prefijo):]
        return valor

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
