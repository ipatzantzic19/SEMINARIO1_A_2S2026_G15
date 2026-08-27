"""Tests del guard de autenticación (app/seguridad.py), en particular la
mitigación de interoperabilidad con Node: Node firma "sub" como número
(ver app/autenticacion/service.py, comentario en iniciar_sesion) y un token
suyo puede llegar aquí a través del balanceador de carga."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
from app.errors import ApiError
from app.seguridad import obtener_usuario_actual

RUTA_PERFIL = "/api/v1/perfil"


def _token(sub, **extra_claims) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(seconds=3600)).timestamp()),
        **extra_claims,
    }
    return jwt.encode(payload, get_settings().secreto_jwt, algorithm="HS256")


def test_guard_acepta_sub_string_estilo_python():
    token = _token("5", email="a@correo.com", name="Ana")

    usuario = obtener_usuario_actual(authorization=f"Bearer {token}")

    assert usuario.usuario_id == 5
    assert usuario.correo_electronico == "a@correo.com"


def test_guard_acepta_sub_numerico_estilo_node():
    """Node emite 'sub' como número (viola RFC 7519); PyJWT lo rechaza por
    defecto con `InvalidSubjectError`. El guard debe tolerarlo igual que un
    'sub' string, normalizando siempre a int."""
    token = _token(5, email="a@correo.com", name="Ana")

    usuario = obtener_usuario_actual(authorization=f"Bearer {token}")

    assert usuario.usuario_id == 5


def test_guard_rechaza_sin_header():
    with pytest.raises(ApiError) as exc_info:
        obtener_usuario_actual(authorization=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.codigo == "ERROR_AUTENTICACION"


def test_guard_rechaza_token_invalido():
    with pytest.raises(ApiError) as exc_info:
        obtener_usuario_actual(authorization="Bearer token-invalido")

    assert exc_info.value.status_code == 401
    assert exc_info.value.codigo == "ERROR_AUTENTICACION"


def test_guard_rechaza_token_expirado():
    ahora = datetime.now(timezone.utc)
    payload = {"sub": "5", "iat": int((ahora - timedelta(hours=2)).timestamp()), "exp": int((ahora - timedelta(hours=1)).timestamp())}
    token = jwt.encode(payload, get_settings().secreto_jwt, algorithm="HS256")

    with pytest.raises(ApiError) as exc_info:
        obtener_usuario_actual(authorization=f"Bearer {token}")

    assert exc_info.value.status_code == 401


def test_perfil_con_sub_numerico_estilo_node_funciona_end_to_end(client):
    """Prueba de integración: un token con 'sub' numérico (como los que emite
    Node) debe poder consultar /api/v1/perfil a través del guard real."""
    respuesta_registro = client.post(
        "/api/v1/autenticacion/registro",
        data={
            "correoElectronico": "nodesub@correo.com",
            "nombreCompleto": "Usuario Node",
            "contrasena": "clave123",
            "confirmacionContrasena": "clave123",
        },
        files={"fotoPerfil": ("foto.png", b"contenido-de-prueba", "image/png")},
    )
    usuario_id = respuesta_registro.json()["datos"]["usuario"]["id"]

    token = _token(usuario_id, email="nodesub@correo.com", name="Usuario Node")

    respuesta = client.get(RUTA_PERFIL, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["usuario"]["id"] == usuario_id
