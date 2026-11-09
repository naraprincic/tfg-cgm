"""Funciones de seguridad para las contraseñas."""

import bcrypt

FACTOR_DE_COSTO = 12  # definido en el apartado Seguridad de la tesis


def generar_hash(contrasena: str) -> str:
    sal = bcrypt.gensalt(rounds=FACTOR_DE_COSTO)
    return bcrypt.hashpw(contrasena.encode("utf-8"), sal).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("utf-8"))
