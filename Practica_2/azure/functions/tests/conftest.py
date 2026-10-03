"""Utilidades de prueba: sin red ni Azure real; el almacenamiento es un doble."""

import base64
import json
import time

import azure.functions as func
import jwt
import pytest

import function_app
from carga import almacenamiento

SECRETO = "secreto-solo-para-pruebas-" * 2
ENDPOINT = "https://practica2semi1a1s2026g15.blob.core.windows.net/"
CONTENEDOR = "practica2semi1a1s2026archivosg15"
URL_BASE = f"{ENDPOINT}{CONTENEDOR}/"

# PNG 1x1 del contrato (70 bytes).
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
PNG = base64.b64decode(PNG_B64)

UUID4 = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"

_FUNCIONES = {
    "upload/image": function_app.subir_imagen,
    "upload/text": function_app.subir_texto,
    "upload/file": function_app.subir_archivo,
}


class AlmacenamientoFalso:
    """Registra las subidas y devuelve la URL con la forma del SDK."""

    def __init__(self):
        self.subidas: list[dict] = []
        self.falla: Exception | None = None
        self.url: str | None = None

    def subir(self, clave, contenido, *, tipo_contenido, disposicion):
        if self.falla is not None:
            raise self.falla
        self.subidas.append(
            {"clave": clave, "contenido": contenido, "tipo_contenido": tipo_contenido, "disposicion": disposicion}
        )
        return self.url if self.url is not None else URL_BASE + clave


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_BLOB_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER_NAME", CONTENEDOR)
    monkeypatch.setenv("JWT_SECRET", SECRETO)
    for nombre in ("UPLOAD_MAX_IMAGE_BYTES", "UPLOAD_MAX_TEXT_BYTES", "UPLOAD_MAX_FILE_BYTES"):
        monkeypatch.delenv(nombre, raising=False)


@pytest.fixture(autouse=True)
def almacen():
    falso = AlmacenamientoFalso()
    almacenamiento.sustituir(falso)
    yield falso
    almacenamiento.sustituir(None)
    almacenamiento._actual = None


def token(sub="15", *, exp_en=3600, secreto=SECRETO, algoritmo="HS256", **extra) -> str:
    claims = {"sub": sub, "nombreUsuario": "ana", "iat": int(time.time()), **extra}
    if exp_en is not None:
        claims["exp"] = int(time.time()) + exp_en
    return jwt.encode(claims, secreto, algorithm=algoritmo)


def b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


class Resultado:
    def __init__(self, respuesta: func.HttpResponse):
        self.estado = respuesta.status_code
        self.texto = respuesta.get_body().decode("utf-8")
        self.json = json.loads(self.texto)
        self.headers = respuesta.headers

    @property
    def detalles(self):
        return self.json["error"].get("detalles")

    @property
    def archivo(self):
        return self.json["datos"]["archivo"]


def llamar(ruta, cuerpo=None, *, auth="token", crudo=None, content_type="application/json") -> Resultado:
    """POST a la función. `auth`: "token" (válido, usuario 15), None (sin header) o el header literal."""
    headers = {}
    if content_type is not None:
        headers["Content-Type"] = content_type
    if auth == "token":
        headers["Authorization"] = f"Bearer {token()}"
    elif auth is not None:
        headers["Authorization"] = auth
    if crudo is None:
        crudo = b"" if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    req = func.HttpRequest(method="POST", url=f"http://localhost/{ruta}", headers=headers, body=crudo)
    return Resultado(_FUNCIONES[ruta].build().get_user_function()(req))


def cuerpo(nombre="archivo.bin", tipo="application/octet-stream", contenido=b"hola", **extra) -> dict:
    datos = {"nombreOriginal": nombre, "tipoMime": tipo, "contenidoBase64": b64(contenido)}
    datos.update(extra)
    return datos


def detalles_de(resultado: Resultado) -> list[tuple]:
    return [(d.get("campo"), d["mensaje"]) for d in resultado.detalles]
