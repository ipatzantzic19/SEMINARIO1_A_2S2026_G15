"""bcrypt, JWT y la dependencia usuario_actual (sin base de datos)."""

import time

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.config import obtener_config
from app.seguridad import (
    UsuarioActual,
    crear_token,
    hashear_contrasena,
    usuario_actual,
    verificar_contrasena,
)

ERROR_401 = {
    "exito": False,
    "error": {
        "codigo": "ERROR_AUTENTICACION",
        "mensaje": "Token de autenticación ausente, inválido o expirado.",
    },
}


@pytest.fixture
def cliente_protegido():
    from app.main import crear_app

    app = crear_app()

    @app.get("/_prueba/protegida")
    def ruta_protegida(usuario: UsuarioActual = Depends(usuario_actual)) -> dict:
        return {"id": usuario.id, "nombreUsuario": usuario.nombre_usuario}

    # Sin ciclo de vida: la dependencia no usa la base de datos.
    return TestClient(app)


def firmar(claims: dict, secreto: str | None = None) -> str:
    return jwt.encode(claims, secreto or obtener_config().jwt_secret, algorithm="HS256")


def test_bcrypt_costo_10_y_verificacion():
    hash_generado = hashear_contrasena("Secreta123")

    assert hash_generado.startswith("$2b$10$")
    assert verificar_contrasena("Secreta123", hash_generado)
    assert not verificar_contrasena("Secreta124", hash_generado)


def test_bcrypt_acepta_hash_2a_de_node():
    # Node (bcryptjs) puede emitir el prefijo $2a$; debe verificarse igual.
    hash_2a = "$2a$" + hashear_contrasena("Secreta123")[4:]

    assert verificar_contrasena("Secreta123", hash_2a)


def test_token_contiene_los_claims_acordados():
    token, expira_en = crear_token(15, "ana_123")
    claims = jwt.decode(token, obtener_config().jwt_secret, algorithms=["HS256"])

    assert expira_en == 3600
    assert claims["sub"] == "15"
    assert claims["nombreUsuario"] == "ana_123"
    assert claims["exp"] - claims["iat"] == 3600
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_token_valido(cliente_protegido):
    token, _ = crear_token(15, "ana_123")

    respuesta = cliente_protegido.get("/_prueba/protegida", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": 15, "nombreUsuario": "ana_123"}


def test_token_con_sub_numerico_de_node(cliente_protegido):
    ahora = int(time.time())
    token = firmar({"sub": 15, "nombreUsuario": "ana_123", "iat": ahora, "exp": ahora + 60})

    respuesta = cliente_protegido.get("/_prueba/protegida", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == 15


@pytest.mark.parametrize(
    "encabezados",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic dXN1YXJpbzpjbGF2ZQ=="},
        {"Authorization": "Bearer no.es.un.jwt"},
        {"Authorization": "Bearer a b"},
    ],
    ids=["sin-header", "vacio", "sin-token", "otro-esquema", "mal-formado", "partes-de-mas"],
)
def test_401_header_ausente_o_mal_formado(cliente_protegido, encabezados):
    respuesta = cliente_protegido.get("/_prueba/protegida", headers=encabezados)

    assert respuesta.status_code == 401
    assert respuesta.json() == ERROR_401


def test_401_firma_invalida(cliente_protegido):
    ahora = int(time.time())
    token = firmar({"sub": "15", "iat": ahora, "exp": ahora + 60}, secreto="otro-secreto-de-al-menos-32-bytes!!")

    respuesta = cliente_protegido.get("/_prueba/protegida", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.json() == ERROR_401


def test_401_token_expirado(cliente_protegido):
    ahora = int(time.time())
    token = firmar({"sub": "15", "nombreUsuario": "ana_123", "iat": ahora - 7200, "exp": ahora - 3600})

    respuesta = cliente_protegido.get("/_prueba/protegida", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.json() == ERROR_401


@pytest.mark.parametrize("sub", ["abc", "0", True, None])
def test_401_sub_invalido(cliente_protegido, sub):
    ahora = int(time.time())
    claims = {"iat": ahora, "exp": ahora + 60}
    if sub is not None:
        claims["sub"] = sub

    respuesta = cliente_protegido.get(
        "/_prueba/protegida", headers={"Authorization": f"Bearer {firmar(claims)}"}
    )

    assert respuesta.status_code == 401


def test_401_algoritmo_none_rechazado(cliente_protegido):
    ahora = int(time.time())
    token = jwt.encode({"sub": "15", "iat": ahora, "exp": ahora + 60}, key=None, algorithm="none")

    respuesta = cliente_protegido.get("/_prueba/protegida", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
