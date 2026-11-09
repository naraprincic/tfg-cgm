"""Esquemas: la forma que deben tener los datos que entran y salen de la API."""

import re

from pydantic import BaseModel, EmailStr, ValidationInfo, field_validator


class RegistroUsuario(BaseModel):
    """Datos que se envían para crear una cuenta (HU-001)."""

    email: EmailStr
    contrasena: str
    acepta_consentimiento: bool

    @field_validator("email", "contrasena", mode="before")
    @classmethod
    def no_vacio(cls, valor):
        # Un texto vacío o con solo espacios cuenta como campo incompleto (criterio 3).
        if isinstance(valor, str) and not valor.strip():
            raise ValueError("Este campo es obligatorio.")
        return valor

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        # Se guarda en minúsculas para que "Nara@Mail.com" y "nara@mail.com" sean la misma cuenta.
        return valor.strip().lower()

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, valor: str, info: ValidationInfo) -> str:
        # Reglas del apartado Seguridad / HU-001, criterio 2.
        problemas = []
        if not 8 <= len(valor) <= 64:
            problemas.append("tener entre 8 y 64 caracteres")
        if not re.search(r"[A-Z]", valor):
            problemas.append("incluir al menos una letra mayúscula")
        if not re.search(r"[a-z]", valor):
            problemas.append("incluir al menos una letra minúscula")
        if not re.search(r"[0-9]", valor):
            problemas.append("incluir al menos un número")
        if len(valor.encode("utf-8")) > 72:  # límite técnico de bcrypt
            problemas.append("no superar los 72 bytes (usá menos caracteres especiales)")
        if problemas:
            raise ValueError("La contraseña debe " + ", ".join(problemas) + ".")

        # La contraseña no puede incluir el correo electrónico (apartado Seguridad).
        email = info.data.get("email")
        if email:
            usuario_del_correo = email.split("@")[0]
            contrasena = valor.lower()
            if email in contrasena or (len(usuario_del_correo) >= 3 and usuario_del_correo in contrasena):
                raise ValueError("La contraseña no puede incluir tu correo electrónico.")
        return valor

    @field_validator("acepta_consentimiento")
    @classmethod
    def exigir_consentimiento(cls, valor: bool) -> bool:
        # Ley 25.326, art. 5: los datos de salud requieren consentimiento expreso.
        if not valor:
            raise ValueError(
                "Es necesario aceptar el tratamiento de tus datos de salud para crear la cuenta."
            )
        return valor

class InicioSesion(BaseModel):
    """Datos para iniciar sesión (HU-002)."""

    email: str
    contrasena: str

    @field_validator("email", "contrasena", mode="before")
    @classmethod
    def no_vacio(cls, valor):
        # HU-002, criterio 4: indicar que faltan campos por completar.
        if isinstance(valor, str) and not valor.strip():
            raise ValueError("Este campo es obligatorio.")
        return valor

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return valor.strip().lower()


class UsuarioPublico(BaseModel):
    """Datos del usuario que se pueden mostrar en pantalla."""

    id_usuario: int
    email: str
    rango_min: int
    rango_max: int
    zona_horaria: str


class UsuarioCreado(BaseModel):
    """Respuesta al registrarse. Nunca incluye la contraseña ni su hash."""

    id_usuario: int
    email: str
    mensaje: str
