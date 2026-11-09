"""Conexión con el modelo de lenguaje (API de OpenAI)."""

import json
from datetime import date

from app.config import settings


_uso_diario: dict = {"fecha": None, "pedidos": 0}


def _consumir_cupo() -> None:
    """Cuenta los pedidos del día y corta al llegar al límite de la demo (si está configurado)."""
    limite = settings.limite_ia_diario
    if not limite:
        return
    hoy = date.today()
    if _uso_diario["fecha"] != hoy:
        _uso_diario.update(fecha=hoy, pedidos=0)
    if _uso_diario["pedidos"] >= limite:
        raise ServicioNoDisponible(
            "Se alcanzó el límite diario de usos de la inteligencia artificial de esta demostración. "
            "Podés cargar los eventos de forma manual; el resumen se genera con la plantilla.")
    _uso_diario["pedidos"] += 1


class ServicioNoDisponible(Exception):
    """No hay clave configurada, no hay conexión o el servicio respondió con error."""


def disponible() -> bool:
    return bool(settings.openai_api_key)


def modelo() -> str:
    return settings.modelo_ia


def llamar_json(sistema: str, usuario: str, nombre_esquema: str, esquema: dict) -> dict:
    """Envía un pedido al modelo y exige una respuesta JSON que cumpla `esquema` (salidas estructuradas)."""
    if not disponible():
        raise ServicioNoDisponible("La inteligencia artificial no está configurada (falta OPENAI_API_KEY).")

    _consumir_cupo()
    import openai  # se importa acá para que la aplicación arranque aunque no se use la IA

    try:
        cliente = openai.OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=1)
        respuesta = cliente.chat.completions.create(
            model=settings.modelo_ia,
            temperature=0,  # respuestas lo más estables posible
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": nombre_esquema, "strict": True, "schema": esquema},
            },
        )
    except openai.AuthenticationError as error:
        raise ServicioNoDisponible("La clave de OpenAI no es válida: revisá OPENAI_API_KEY en el archivo .env.") from error
    except openai.RateLimitError as error:
        if "insufficient_quota" in str(getattr(error, "code", "")) + str(getattr(error, "body", "")):
            raise ServicioNoDisponible("La cuenta de OpenAI no tiene saldo disponible.") from error
        raise ServicioNoDisponible("OpenAI rechazó el pedido por exceso de solicitudes: esperá un minuto y probá de nuevo.") from error
    except openai.NotFoundError as error:
        raise ServicioNoDisponible(f"La clave no tiene acceso al modelo {settings.modelo_ia}.") from error
    except openai.OpenAIError as error:
        raise ServicioNoDisponible(f"El servicio de inteligencia artificial no respondió ({error.__class__.__name__}).") from error

    mensaje = respuesta.choices[0].message
    if getattr(mensaje, "refusal", None):
        raise ServicioNoDisponible("El modelo se negó a responder el pedido.")
    try:
        return json.loads(mensaje.content or "")
    except json.JSONDecodeError as error:
        raise ValueError("La respuesta del modelo no es un JSON válido.") from error
