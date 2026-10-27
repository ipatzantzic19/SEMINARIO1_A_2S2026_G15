"""Registro y login contra PostgreSQL real (docker-compose.yml).

Se omiten automáticamente si la base de desarrollo no responde.
"""

import jwt
import pytest

from app.config import obtener_config
from app.seguridad import usuario_actual

pytestmark = pytest.mark.integracion

REGISTRO = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"


def registro(**cambios) -> dict:
    datos = {
        "nombreUsuario": "ana_123",
        "correoElectronico": "ana@example.com",
        "contrasena": "Secreta123",
        "confirmacionContrasena": "Secreta123",
    }
    datos.update(cambios)
    return datos


def assert_conflicto(respuesta, campos: list[str]) -> None:
    assert respuesta.status_code == 409
    error = respuesta.json()["error"]
    assert respuesta.json()["exito"] is False
    assert error["codigo"] == "CONFLICTO"
    assert error["mensaje"] == "El nombre de usuario o el correo electrónico ya están registrados."
    assert [d["campo"] for d in error["detalles"]] == campos


def test_registro_exitoso(cliente_bd):
    respuesta = cliente_bd.post(
        REGISTRO, json=registro(urlImagenPerfil="https://bucket.example.com/profiles/1/a.png")
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo == {
        "exito": True,
        "datos": {
            "usuario": {
                "id": cuerpo["datos"]["usuario"]["id"],
                "nombreUsuario": "ana_123",
                "correoElectronico": "ana@example.com",
                "urlImagenPerfil": "https://bucket.example.com/profiles/1/a.png",
            }
        },
    }
    assert isinstance(cuerpo["datos"]["usuario"]["id"], int)
    assert "hash" not in respuesta.text.lower()


def test_registro_sin_imagen_devuelve_null(cliente_bd):
    respuesta = cliente_bd.post(REGISTRO, json=registro())

    assert respuesta.status_code == 201
    assert respuesta.json()["datos"]["usuario"]["urlImagenPerfil"] is None


def test_409_usuario_repetido(cliente_bd):
    cliente_bd.post(REGISTRO, json=registro())

    respuesta = cliente_bd.post(REGISTRO, json=registro(correoElectronico="otra@example.com"))

    assert_conflicto(respuesta, ["nombreUsuario"])


def test_409_correo_repetido(cliente_bd):
    cliente_bd.post(REGISTRO, json=registro())

    respuesta = cliente_bd.post(REGISTRO, json=registro(nombreUsuario="otro_usuario"))

    assert_conflicto(respuesta, ["correoElectronico"])


def test_409_usuario_y_correo_repetidos_en_un_solo_error(cliente_bd):
    cliente_bd.post(REGISTRO, json=registro())

    respuesta = cliente_bd.post(REGISTRO, json=registro())

    assert_conflicto(respuesta, ["nombreUsuario", "correoElectronico"])


def test_normalizacion_de_mayusculas(cliente_bd):
    respuesta = cliente_bd.post(
        REGISTRO, json=registro(nombreUsuario="  ANA_123 ", correoElectronico="  Ana@Example.COM ")
    )

    assert respuesta.status_code == 201
    usuario = respuesta.json()["datos"]["usuario"]
    assert usuario["nombreUsuario"] == "ana_123"
    assert usuario["correoElectronico"] == "ana@example.com"

    # La misma identidad con otras mayúsculas choca con la ya registrada.
    respuesta = cliente_bd.post(REGISTRO, json=registro(nombreUsuario="Ana_123", correoElectronico="ANA@EXAMPLE.COM"))
    assert_conflicto(respuesta, ["nombreUsuario", "correoElectronico"])


def test_login_correcto(cliente_bd):
    cliente_bd.post(REGISTRO, json=registro())

    respuesta = cliente_bd.post(LOGIN, json={"nombreUsuario": " ANA_123 ", "contrasena": "Secreta123"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is True
    datos = cuerpo["datos"]
    assert datos["tipoToken"] == "Bearer"
    assert datos["expiraEn"] == 3600
    assert datos["usuario"]["nombreUsuario"] == "ana_123"
    assert set(datos["usuario"]) == {"id", "nombreUsuario", "correoElectronico", "urlImagenPerfil"}

    claims = jwt.decode(datos["token"], obtener_config().jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == str(datos["usuario"]["id"])
    assert claims["nombreUsuario"] == "ana_123"


def test_token_del_login_es_aceptado_por_usuario_actual(cliente_bd):
    cliente_bd.post(REGISTRO, json=registro())
    datos = cliente_bd.post(LOGIN, json={"nombreUsuario": "ana_123", "contrasena": "Secreta123"}).json()["datos"]

    usuario = usuario_actual(authorization=f"Bearer {datos['token']}")

    assert usuario.id == datos["usuario"]["id"]
    assert usuario.nombre_usuario == "ana_123"


def test_login_usuario_inexistente_y_contrasena_incorrecta_mismo_401(cliente_bd):
    cliente_bd.post(REGISTRO, json=registro())

    inexistente = cliente_bd.post(LOGIN, json={"nombreUsuario": "nadie", "contrasena": "Secreta123"})
    incorrecta = cliente_bd.post(LOGIN, json={"nombreUsuario": "ana_123", "contrasena": "Equivocada1"})

    esperado = {
        "exito": False,
        "error": {"codigo": "ERROR_AUTENTICACION", "mensaje": "Nombre de usuario o contraseña incorrectos."},
    }
    assert inexistente.status_code == incorrecta.status_code == 401
    assert inexistente.json() == incorrecta.json() == esperado


def test_registro_guarda_hash_2b_costo_10(cliente_bd):
    import psycopg

    from app.database import construir_conninfo

    cliente_bd.post(REGISTRO, json=registro())

    with psycopg.connect(construir_conninfo(obtener_config())) as conn:
        hash_guardado = conn.execute("SELECT contrasena_hash FROM usuarios").fetchone()[0]
    assert hash_guardado.startswith("$2b$10$")
