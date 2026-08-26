import hashlib

import jwt

from app.config import get_settings
from app.database import get_cursor
from tests.conftest import archivo_imagen_de_prueba

RUTA_REGISTRO = "/api/v1/autenticacion/registro"
RUTA_LOGIN = "/api/v1/autenticacion/inicio-sesion"


def _registrar(
    client,
    correo="usuario@example.com",
    nombre="Usuario Ejemplo",
    contrasena="clave123",
    confirmacion=None,
    content_type="image/png",
):
    if confirmacion is None:
        confirmacion = contrasena
    data = {
        "correoElectronico": correo,
        "nombreCompleto": nombre,
        "contrasena": contrasena,
        "confirmacionContrasena": confirmacion,
    }
    files = archivo_imagen_de_prueba(content_type=content_type)
    return client.post(RUTA_REGISTRO, data=data, files=files)


def test_registro_exitoso(client):
    respuesta = _registrar(client, correo="  Nuevo@Correo.com ")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is True
    usuario = cuerpo["datos"]["usuario"]
    assert usuario["correoElectronico"] == "nuevo@correo.com"
    assert usuario["nombreCompleto"] == "Usuario Ejemplo"
    assert isinstance(usuario["id"], int)
    assert usuario["urlFotoPerfil"].startswith(
        f"https://{get_settings().bucket_imagenes}.s3.{get_settings().region_aws}.amazonaws.com/Fotos_Perfil/"
    )


def test_registro_guarda_hash_md5_exacto(client):
    _registrar(client, correo="hash@correo.com", contrasena="clave123")

    with get_cursor() as cur:
        cur.execute("SELECT contrasena_md5 FROM usuarios WHERE correo_electronico = %s", ("hash@correo.com",))
        fila = cur.fetchone()

    assert fila is not None
    assert fila["contrasena_md5"] == hashlib.md5("clave123".encode("utf-8")).hexdigest()


def test_registro_correo_duplicado(client):
    _registrar(client, correo="duplicado@correo.com")
    respuesta = _registrar(client, correo="duplicado@correo.com")

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is False
    assert cuerpo["error"]["codigo"] == "CONFLICTO"


def test_registro_password_no_coincide(client):
    respuesta = _registrar(client, contrasena="clave123", confirmacion="otraclave")

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ERROR_VALIDACION"


def test_registro_tipo_imagen_no_soportado(client):
    respuesta = _registrar(client, content_type="text/plain")

    assert respuesta.status_code == 415
    assert respuesta.json()["error"]["codigo"] == "TIPO_CONTENIDO_NO_SOPORTADO"


def test_registro_correo_formato_invalido(client):
    respuesta = _registrar(client, correo="no-es-un-correo")

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ERROR_VALIDACION"


def test_registro_sin_foto_perfil(client):
    data = {
        "correoElectronico": "sinfoto@correo.com",
        "nombreCompleto": "Usuario Ejemplo",
        "contrasena": "clave123",
        "confirmacionContrasena": "clave123",
    }
    respuesta = client.post(RUTA_REGISTRO, data=data)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ERROR_VALIDACION"


def test_login_exitoso(client):
    _registrar(client, correo="login@correo.com", contrasena="clave123")

    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": "login@correo.com", "contrasena": "clave123"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is True
    datos = cuerpo["datos"]
    assert datos["tipoToken"] == "Bearer"
    assert datos["expiraEn"] == 3600
    assert datos["usuario"]["correoElectronico"] == "login@correo.com"

    payload = jwt.decode(datos["token"], get_settings().secreto_jwt, algorithms=["HS256"])
    assert payload["email"] == "login@correo.com"
    assert payload["exp"] - payload["iat"] == 3600
    # "sub" va como string por especificación JWT (RFC 7519) — PyJWT lo exige al
    # decodificar. Ver la nota en app/autenticacion/service.py::iniciar_sesion.
    assert payload["sub"] == str(datos["usuario"]["id"])


def test_login_correo_normalizado_igual_que_en_registro(client):
    _registrar(client, correo="  MAYUS@Correo.com  ", contrasena="clave123")

    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": "mayus@correo.com", "contrasena": "clave123"})

    assert respuesta.status_code == 200


def test_login_credenciales_invalidas(client):
    _registrar(client, correo="malaclave@correo.com", contrasena="clave123")

    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": "malaclave@correo.com", "contrasena": "incorrecta"})

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_login_usuario_inexistente(client):
    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": "nadie@correo.com", "contrasena": "clave123"})

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_login_correo_formato_invalido(client):
    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": "no-es-un-correo", "contrasena": "clave123"})

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ERROR_VALIDACION"
