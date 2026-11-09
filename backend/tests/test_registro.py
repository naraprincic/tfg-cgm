"""Pruebas automáticas de la HU-001 – Registro del usuario."""

from sqlalchemy import select

from app.models import Usuario
from app.seguridad import verificar_contrasena

DATOS_VALIDOS = {
    "email": "prueba@example.com",
    "contrasena": "Glucosa2026",
    "acepta_consentimiento": True,
}


def registrar(cliente, **cambios):
    return cliente.post("/auth/registro", json={**DATOS_VALIDOS, **cambios})


def mensajes(respuesta):
    return {e["campo"]: e["mensaje"] for e in respuesta.json()["errores"]}


# --- Criterio 4: registro válido --------------------------------------------

def test_registro_valido_guarda_hash_y_configuracion_inicial(cliente, db):
    respuesta = registrar(cliente)
    assert respuesta.status_code == 201
    assert "contrasena" not in respuesta.json()  # la respuesta nunca devuelve la contraseña

    usuario = db.scalar(select(Usuario).where(Usuario.email == "prueba@example.com"))
    assert usuario.contrasena_hash != "Glucosa2026"            # no se guarda en texto plano
    assert usuario.contrasena_hash.startswith("$2b$12$")       # bcrypt con factor de costo 12
    assert verificar_contrasena("Glucosa2026", usuario.contrasena_hash)
    assert usuario.fecha_consentimiento is not None             # consentimiento registrado
    assert usuario.configuracion.rango_min == 70
    assert usuario.configuracion.rango_max == 180


def test_email_se_guarda_en_minusculas(cliente, db):
    registrar(cliente, email="  Prueba@EXAMPLE.com ")
    assert db.scalar(select(Usuario.email)) == "prueba@example.com"


# --- Criterio 1: correo ya registrado ---------------------------------------

def test_correo_repetido_muestra_error(cliente):
    registrar(cliente)
    respuesta = registrar(cliente, email="PRUEBA@example.com")  # mismo correo, otras mayúsculas
    assert respuesta.status_code == 409
    assert "Ya existe una cuenta" in respuesta.json()["detail"]


# --- Criterio 2: contraseña inválida ----------------------------------------

def test_contrasena_corta(cliente):
    respuesta = registrar(cliente, contrasena="Ab1")
    assert respuesta.status_code == 422
    assert "entre 8 y 64" in mensajes(respuesta)["contrasena"]


def test_contrasena_sin_numeros(cliente):
    respuesta = registrar(cliente, contrasena="SoloLetras")
    assert respuesta.status_code == 422
    assert "número" in mensajes(respuesta)["contrasena"]


def test_contrasena_sin_mayuscula(cliente):
    respuesta = registrar(cliente, contrasena="glucosa2026")
    assert respuesta.status_code == 422
    assert "mayúscula" in mensajes(respuesta)["contrasena"]


def test_contrasena_no_puede_incluir_el_correo(cliente):
    respuesta = registrar(cliente, contrasena="Prueba2026")  # contiene "prueba"
    assert respuesta.status_code == 422
    assert "correo" in mensajes(respuesta)["contrasena"]


# --- Criterio 3: campos obligatorios incompletos ----------------------------

def test_campos_faltantes_se_indican_todos(cliente):
    respuesta = cliente.post("/auth/registro", json={})
    assert respuesta.status_code == 422
    errores = mensajes(respuesta)
    assert set(errores) == {"email", "contrasena", "acepta_consentimiento"}
    assert all(m == "Este campo es obligatorio." for m in errores.values())


def test_campos_vacios_cuentan_como_incompletos(cliente):
    respuesta = registrar(cliente, email="", contrasena="   ")
    errores = mensajes(respuesta)
    assert errores["email"] == "Este campo es obligatorio."
    assert errores["contrasena"] == "Este campo es obligatorio."


def test_email_con_formato_invalido(cliente):
    respuesta = registrar(cliente, email="esto-no-es-un-correo")
    assert mensajes(respuesta)["email"] == "El correo electrónico no tiene un formato válido."


# --- Consentimiento (Ley 25.326, art. 5) ------------------------------------

def test_sin_consentimiento_no_se_crea_la_cuenta(cliente, db):
    respuesta = registrar(cliente, acepta_consentimiento=False)
    assert respuesta.status_code == 422
    assert "consentimiento" in mensajes(respuesta)["acepta_consentimiento"] or \
        "aceptar" in mensajes(respuesta)["acepta_consentimiento"]
    assert db.scalar(select(Usuario)) is None
