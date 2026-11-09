"""Carga la cuenta de demostración con datos sintéticos (para la demo en línea y para probar rápido)."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.main import app
from app.models import Usuario

EMAIL = "demo@prototipo.com"
CONTRASENA = "Glucosa2026"
DATOS = Path(__file__).resolve().parents[2] / "datos_prueba"

IMPORTACIONES = [
    ("libreview_14dias.csv", "mes-dia"),
    ("dexcom_14dias.csv", None),
    ("generico_1dia.csv", None),
    ("generico_con_errores.csv", None),
    ("dexcom_noviembre.csv", None),
]

EVENTOS = [
    ("2026-10-31", "comida", "Milanesa con puré", "12:50", None, None),
    ("2026-10-31", "insulina", "Insulina rápida", "12:45", 6, "unidades"),
    ("2026-10-31", "actividad_fisica", "Caminata", "16:00", 40, "minutos"),
    ("2026-10-31", "comida", "Cena: fideos con salsa", "21:00", None, None),
    ("2026-10-16", "comida", "Desayuno: tostadas con queso", "07:30", 2, "porciones"),
    ("2026-10-16", "comida", "Almuerzo: ensalada y pollo", "12:40", None, None),
    ("2026-10-16", "insulina", "Insulina rápida", "12:35", 5, "unidades"),
    ("2026-10-16", "sintoma", "Mareo leve", "04:20", None, None),
    ("2026-10-29", "actividad_fisica", "Bicicleta", "18:00", 45, "minutos"),
    ("2026-10-29", "comida", "Merienda: banana", "17:00", None, None),
    ("2026-11-08", "comida", "Desayuno: café con leche y tostadas", "08:15", None, None),
    ("2026-11-08", "insulina", "Insulina rápida", "13:05", 5, "unidades"),
    ("2026-11-08", "comida", "Almuerzo: arroz con pollo", "13:10", None, None),
    ("2026-11-08", "actividad_fisica", "Caminata", "10:30", 30, "minutos"),
    ("2026-11-08", "comida", "Merienda: yogur con frutas", "18:15", None, None),
    ("2026-11-08", "comida", "Cena: tarta de verduras", "21:15", None, None),
]

RESUMENES = ["2026-11-08", "2026-10-31", "2026-10-16", "2026-10-29"]


def borrar_cuenta_anterior() -> None:
    with SessionLocal() as db:
        id_usuario = db.scalar(select(Usuario.id_usuario).where(Usuario.email == EMAIL))
        if id_usuario is not None:
            # Las tablas tienen ON DELETE CASCADE: al borrar el usuario se borran todos sus datos.
            db.execute(delete(Usuario).where(Usuario.id_usuario == id_usuario))
            db.commit()
            print("Cuenta demo anterior borrada.")


def main() -> None:
    borrar_cuenta_anterior()
    with TestClient(app, base_url="https://localhost") as api:
        r = api.post("/auth/registro", json={"email": EMAIL, "contrasena": CONTRASENA, "acepta_consentimiento": True})
        r.raise_for_status()
        r = api.post("/auth/login", json={"email": EMAIL, "contrasena": CONTRASENA})
        r.raise_for_status()

        for nombre, formato in IMPORTACIONES:
            contenido = (DATOS / nombre).read_bytes()
            datos = {"formato_fecha": formato} if formato else {}
            r = api.post("/importaciones", files={"archivo": (nombre, contenido, "text/csv")}, data=datos)
            print(f"Importación {nombre}: {r.status_code}")
            r.raise_for_status()

        for fecha, tipo, descripcion, hora, cantidad, unidad in EVENTOS:
            evento = {"tipo": tipo, "descripcion": descripcion, "fecha_hora": f"{fecha}T{hora}",
                      "cantidad": cantidad, "unidad": unidad}
            r = api.post("/eventos", json=evento)
            r.raise_for_status()
        print(f"Eventos registrados: {len(EVENTOS)}")

        for fecha in RESUMENES:
            r = api.post(f"/dias/{fecha}/resumen")
            r.raise_for_status()
            print(f"Resumen del {fecha}: {r.json()['estado_verificacion']}")

    print(f"Listo. Cuenta demo: {EMAIL} / {CONTRASENA}")


if __name__ == "__main__":
    main()
