"""Pruebas automáticas de la HU-002 (inicio de sesión), la HU-003 (cierre de sesión) y las reglas de acceso del apartado Seguridad."""

from datetime import timedelta

from sqlalchemy import select

from app.models import Sesion, ahora_utc

CUENTA = {"email": "nara@example.com", "contrasena": "Glucosa2026", "acepta_consentimiento": True}


def crear_cuenta(cliente, email="nara@example.com"):
    cliente.post("/auth/registro", json={**CUENTA, "email": email})


def iniciar(cliente, email="nara@example.com", contrasena="Glucosa2026"):
    return cliente.post("/auth/login", json={"email": email, "contrasena": contrasena})


# --- HU-002, criterio 1: credenciales correctas -----------------------------

def test_login_correcto_crea_sesion_con_cookie_httponly(cliente, db):
    crear_cuenta(cliente)
    respuesta = iniciar(cliente, email="NARA@example.com")  # el correo no distingue mayúsculas
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == "nara@example.com"
    cookie = respuesta.headers["set-cookie"]
    assert "sesion=" in cookie and "HttpOnly" in cookie
    # En la base no se guarda el token, solo su hash.
    token = cliente.cookies.get("sesion")
    assert db.scalar(select(Sesion.token_hash)) != token
    assert cliente.get("/auth/yo").status_code == 200


# --- HU-002, criterio 2: credenciales incorrectas ---------------------------

def test_credenciales_incorrectas_no_dicen_que_campo_fallo(cliente):
    crear_cuenta(cliente)
    clave_mal = iniciar(cliente, contrasena="OtraClave99")
    correo_mal = iniciar(cliente, email="nadie@example.com")
    assert clave_mal.status_code == correo_mal.status_code == 401
    assert clave_mal.json()["detail"] == correo_mal.json()["detail"]


# --- HU-002, criterio 3: solo los datos propios -----------------------------

def test_sin_sesion_no_se_accede_a_datos(cliente):
    assert cliente.get("/auth/yo").status_code == 401
    assert cliente.get("/importaciones").status_code == 401
    assert cliente.get("/mediciones/dias").status_code == 401


# --- HU-002, criterio 4: campos incompletos ---------------------------------

def test_campos_incompletos_se_indican(cliente):
    respuesta = cliente.post("/auth/login", json={"email": "", "contrasena": ""})
    assert respuesta.status_code == 422
    campos = {e["campo"] for e in respuesta.json()["errores"]}
    assert campos == {"email", "contrasena"}


# --- HU-002, criterio 5: cierre por inactividad -----------------------------

def test_sesion_se_cierra_tras_30_minutos_sin_actividad(cliente, db):
    crear_cuenta(cliente)
    iniciar(cliente)
    sesion = db.scalar(select(Sesion))
    sesion.ultimo_uso = ahora_utc() - timedelta(minutes=31)
    db.commit()
    respuesta = cliente.get("/auth/yo")
    assert respuesta.status_code == 401
    assert "inactividad" in respuesta.json()["detail"]
    assert db.scalar(select(Sesion)) is None  # la sesión se eliminó


def test_la_actividad_mantiene_la_sesion(cliente, db):
    crear_cuenta(cliente)
    iniciar(cliente)
    sesion = db.scalar(select(Sesion))
    sesion.ultimo_uso = ahora_utc() - timedelta(minutes=29)
    db.commit()
    assert cliente.get("/auth/yo").status_code == 200


# --- Seguridad: bloqueo tras cinco intentos fallidos ------------------------

def test_cinco_intentos_fallidos_bloquean_la_cuenta(cliente):
    crear_cuenta(cliente)
    for _ in range(5):
        assert iniciar(cliente, contrasena="Incorrecta1").status_code == 401
    # Bloqueada: ni siquiera la contraseña correcta funciona durante 15 minutos.
    respuesta = iniciar(cliente)
    assert respuesta.status_code == 429
    assert "bloqueada" in respuesta.json()["detail"]


def test_un_inicio_correcto_reinicia_el_contador(cliente):
    crear_cuenta(cliente)
    for _ in range(4):
        iniciar(cliente, contrasena="Incorrecta1")
    assert iniciar(cliente).status_code == 200
    for _ in range(4):
        iniciar(cliente, contrasena="Incorrecta1")
    assert iniciar(cliente).status_code == 200


# --- HU-003: cierre de sesión -----------------------------------------------

def test_cerrar_sesion_revoca_el_token(cliente, db):
    crear_cuenta(cliente)
    iniciar(cliente)
    token = cliente.cookies.get("sesion")
    assert cliente.post("/auth/logout").status_code == 204
    assert db.scalar(select(Sesion)) is None
    # Aunque alguien conserve el token viejo (botón "atrás", copia de la cookie), ya no sirve.
    cliente.cookies.set("sesion", token)
    assert cliente.get("/auth/yo").status_code == 401
