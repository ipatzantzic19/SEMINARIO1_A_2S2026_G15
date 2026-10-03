"""Metadatos de archivos contra PostgreSQL real. Se omite si la base de desarrollo no responde."""

import re

import pytest

pytestmark = pytest.mark.integracion

ARCHIVOS = "/api/v1/files"
FORMATO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
NO_ENCONTRADO = {"exito": False, "error": {"codigo": "NO_ENCONTRADO", "mensaje": "El archivo no existe."}}

ARCHIVO_S3 = {
    "nombreOriginal": "documento.txt",
    "tipoMime": "text/plain",
    "tamanoBytes": 58,
    "proveedorAlmacenamiento": "S3",
    "claveObjeto": "files/1/uuid-documento.txt",
    "urlObjeto": "https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/files/1/uuid-documento.txt",
}
ARCHIVO_BLOB = {
    "nombreOriginal": "foto.png",
    "tipoMime": "image/png",
    "tamanoBytes": 0,
    "proveedorAlmacenamiento": "BLOB",
    "claveObjeto": "files/1/uuid-foto.png",
    "urlObjeto": "https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/files/1/uuid-foto.png",
}


def registrar(cliente, headers, datos: dict) -> dict:
    respuesta = cliente.post(ARCHIVOS, json=datos, headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["datos"]["archivo"]


@pytest.mark.parametrize("datos", [ARCHIVO_S3, ARCHIVO_BLOB], ids=["S3", "BLOB"])
def test_flujo_completo(cliente_bd, autenticar, datos):
    headers = autenticar("ana")

    # Registrar
    respuesta = cliente_bd.post(ARCHIVOS, json=datos, headers=headers)
    assert respuesta.status_code == 201
    assert respuesta.json()["exito"] is True
    archivo = respuesta.json()["datos"]["archivo"]
    assert {k: archivo[k] for k in datos} == datos
    assert set(archivo) == set(datos) | {"id", "usuarioId", "creadoEn"}
    assert FORMATO_FECHA.match(archivo["creadoEn"])
    ruta = f"{ARCHIVOS}/{archivo['id']}"

    # Listar
    assert cliente_bd.get(ARCHIVOS, headers=headers).json()["datos"] == {"archivos": [archivo], "total": 1}

    # Obtener
    respuesta = cliente_bd.get(ruta, headers=headers)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"exito": True, "datos": {"archivo": archivo}}

    # Eliminar (solo el registro)
    respuesta = cliente_bd.delete(ruta, headers=headers)
    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert cliente_bd.get(ruta, headers=headers).json() == NO_ENCONTRADO
    assert cliente_bd.delete(ruta, headers=headers).status_code == 404


def test_orden_mas_reciente_primero(cliente_bd, autenticar):
    headers = autenticar("ana")
    primero = registrar(cliente_bd, headers, {**ARCHIVO_S3, "nombreOriginal": "1.txt"})
    segundo = registrar(cliente_bd, headers, {**ARCHIVO_BLOB, "nombreOriginal": "2.png"})
    tercero = registrar(cliente_bd, headers, {**ARCHIVO_S3, "nombreOriginal": "3.txt"})

    datos = cliente_bd.get(ARCHIVOS, headers=headers).json()["datos"]

    assert [a["id"] for a in datos["archivos"]] == [tercero["id"], segundo["id"], primero["id"]]
    assert datos["total"] == 3


def test_tamano_grande_bigint(cliente_bd, autenticar):
    headers = autenticar("ana")

    archivo = registrar(cliente_bd, headers, {**ARCHIVO_S3, "tamanoBytes": 5 * 1024**4})

    assert archivo["tamanoBytes"] == 5 * 1024**4


@pytest.mark.parametrize("metodo", ["GET", "DELETE"])
def test_404_archivo_inexistente(cliente_bd, autenticar, metodo):
    headers = autenticar("ana")

    respuesta = cliente_bd.request(metodo, f"{ARCHIVOS}/999999", headers=headers)

    assert respuesta.status_code == 404
    assert respuesta.json() == NO_ENCONTRADO


def test_aislamiento_entre_usuarios(cliente_bd, autenticar):
    headers_a = autenticar("usuario_a")
    headers_b = autenticar("usuario_b")
    archivo_a = registrar(cliente_bd, headers_a, ARCHIVO_S3)
    ruta = f"{ARCHIVOS}/{archivo_a['id']}"

    assert cliente_bd.get(ARCHIVOS, headers=headers_b).json()["datos"] == {"archivos": [], "total": 0}
    for respuesta in (cliente_bd.get(ruta, headers=headers_b), cliente_bd.delete(ruta, headers=headers_b)):
        assert respuesta.status_code == 404
        assert respuesta.json() == NO_ENCONTRADO

    assert cliente_bd.get(ruta, headers=headers_a).json()["datos"]["archivo"] == archivo_a


def test_usuario_id_sale_del_token(cliente_bd, autenticar):
    headers_a = autenticar("usuario_a")
    headers_b = autenticar("usuario_b")
    id_a = registrar(cliente_bd, headers_a, ARCHIVO_S3)["usuarioId"]

    archivo_b = registrar(cliente_bd, headers_b, ARCHIVO_S3)

    assert archivo_b["usuarioId"] != id_a
