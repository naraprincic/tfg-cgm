"""Manejo de sesiones (HU-002 / HU-003 y apartado Seguridad)."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Sesion, Usuario, ahora_utc, como_utc

NOMBRE_COOKIE = "sesion"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def crear_sesion(db: Session, usuario: Usuario, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    db.add(Sesion(id_usuario=usuario.id_usuario, token_hash=_hash_token(token)))
    db.commit()
    response.set_cookie(
        key=NOMBRE_COOKIE,
        value=token,
        httponly=True,                   # inaccesible desde JavaScript
        secure=settings.cookie_segura,   # solo por HTTPS en la nube
        samesite="lax",
        path="/",
    )


def cerrar_sesion(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(NOMBRE_COOKIE)
    if token:
        sesion = db.scalar(select(Sesion).where(Sesion.token_hash == _hash_token(token)))
        if sesion:
            db.delete(sesion)  # el token queda revocado en el servidor (HU-003)
            db.commit()
    response.delete_cookie(NOMBRE_COOKIE, path="/")


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Dependencia que usan todos los endpoints privados: devuelve el usuario dueño de la sesión o responde 401."""
    token = request.cookies.get(NOMBRE_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Iniciá sesión para continuar.")

    sesion = db.scalar(select(Sesion).where(Sesion.token_hash == _hash_token(token)))
    if not sesion:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Iniciá sesión para continuar.")

    ahora = ahora_utc()
    if ahora - como_utc(sesion.ultimo_uso) > timedelta(minutes=settings.minutos_inactividad):
        db.delete(sesion)
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Tu sesión se cerró por inactividad. Volvé a iniciar sesión.",
        )

    sesion.ultimo_uso = ahora
    db.commit()
    return db.get(Usuario, sesion.id_usuario)
