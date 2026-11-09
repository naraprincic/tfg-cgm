"""Endpoints de acceso a la aplicación: registro (HU-001), inicio de sesión (HU-002) y cierre de sesión (HU-003)."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import ControlAcceso, Configuracion, Usuario, ahora_utc, como_utc
from app.schemas import InicioSesion, RegistroUsuario, UsuarioCreado, UsuarioPublico
from app.seguridad import generar_hash, verificar_contrasena
from app.sesiones import cerrar_sesion, crear_sesion, usuario_actual

router = APIRouter(prefix="/auth", tags=["Acceso"])

MENSAJE_EMAIL_REPETIDO = "Ya existe una cuenta registrada con ese correo electrónico."
# HU-002, criterio 2: el error no indica cuál de los dos campos falló.
MENSAJE_CREDENCIALES = "El correo electrónico o la contraseña son incorrectos."
# Hash de relleno: si el correo no existe, igual se hace una verificación de bcrypt para que el tiempo de respuesta no revele qué correos están registrados.
_HASH_DE_RELLENO = generar_hash("RellenoNoUsar1")


@router.post("/registro", response_model=UsuarioCreado, status_code=status.HTTP_201_CREATED)
def registrar_usuario(datos: RegistroUsuario, db: Session = Depends(get_db)):
    """Crea una cuenta nueva (HU-001)."""
    # Criterio 1: correo ya registrado.
    existe = db.scalar(select(Usuario).where(Usuario.email == datos.email))
    if existe:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MENSAJE_EMAIL_REPETIDO)

    # Criterio 4: contraseña cifrada + configuración inicial.
    usuario = Usuario(
        email=datos.email,
        contrasena_hash=generar_hash(datos.contrasena),
        fecha_consentimiento=ahora_utc(),
        configuracion=Configuracion(),  # toma los valores iniciales 70–180 mg/dL
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        # Por si dos registros con el mismo correo llegan al mismo tiempo.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MENSAJE_EMAIL_REPETIDO)
    db.refresh(usuario)

    return UsuarioCreado(
        id_usuario=usuario.id_usuario,
        email=usuario.email,
        mensaje="Cuenta creada correctamente.",
    )


def _a_publico(usuario: Usuario) -> UsuarioPublico:
    return UsuarioPublico(
        id_usuario=usuario.id_usuario,
        email=usuario.email,
        rango_min=usuario.configuracion.rango_min,
        rango_max=usuario.configuracion.rango_max,
        zona_horaria=usuario.configuracion.zona_horaria,
    )


@router.post("/login", response_model=UsuarioPublico)
def iniciar_sesion(datos: InicioSesion, response: Response, db: Session = Depends(get_db)):
    """Inicia sesión con correo y contraseña (HU-002)."""
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos.email))
    if usuario is None:
        verificar_contrasena(datos.contrasena, _HASH_DE_RELLENO)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAJE_CREDENCIALES)

    control = db.get(ControlAcceso, usuario.id_usuario)
    if control is None:
        control = ControlAcceso(id_usuario=usuario.id_usuario, intentos_fallidos=0)
        db.add(control)

    ahora = ahora_utc()
    if control.bloqueado_hasta and como_utc(control.bloqueado_hasta) > ahora:
        minutos = int((como_utc(control.bloqueado_hasta) - ahora).total_seconds() // 60) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"La cuenta está bloqueada por demasiados intentos fallidos. Probá de nuevo en {minutos} minutos.",
        )

    if not verificar_contrasena(datos.contrasena, usuario.contrasena_hash):
        control.intentos_fallidos = (control.intentos_fallidos or 0) + 1
        if control.intentos_fallidos >= settings.max_intentos_fallidos:
            control.bloqueado_hasta = ahora + timedelta(minutes=settings.minutos_bloqueo)
            control.intentos_fallidos = 0
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAJE_CREDENCIALES)

    # Inicio correcto: se reinicia el contador y se crea la sesión.
    control.intentos_fallidos = 0
    control.bloqueado_hasta = None
    crear_sesion(db, usuario, response)
    return _a_publico(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar(request: Request, response: Response, db: Session = Depends(get_db)):
    """Cierra la sesión y revoca el token en el servidor (HU-003)."""
    cerrar_sesion(db, request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/yo", response_model=UsuarioPublico)
def quien_soy(usuario: Usuario = Depends(usuario_actual)):
    """Devuelve el usuario de la sesión activa (lo usa el frontend para saber si hay sesión)."""
    return _a_publico(usuario)
