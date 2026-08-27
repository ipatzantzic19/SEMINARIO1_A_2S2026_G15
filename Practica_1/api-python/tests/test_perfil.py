from app.database import get_cursor
from tests.conftest import archivo_imagen_de_prueba

RUTA_PERFIL = "/api/v1/perfil"
RUTA_REGISTRO = "/api/v1/autenticacion/registro"
RUTA_LOGIN = "/api/v1/autenticacion/inicio-sesion"


def _registrar_y_loguear(
    client,
    correo="perfil@correo.com",
    nombre="Usuario Perfil",
    contrasena="clave123",
):
    client.post(
        RUTA_REGISTRO,
        data={
            "correoElectronico": correo,
            "nombreCompleto": nombre,
            "contrasena": contrasena,
            "confirmacionContrasena": contrasena,
        },
        files=archivo_imagen_de_prueba(),
    )
    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": correo, "contrasena": contrasena})
    datos = respuesta.json()["datos"]
    return datos["token"], datos["usuario"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_get_perfil_sin_token_es_rechazado(client):
    respuesta = client.get(RUTA_PERFIL)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_get_perfil_exitoso(client):
    token, usuario = _registrar_y_loguear(client, correo="get@correo.com")

    respuesta = client.get(RUTA_PERFIL, headers=_auth(token))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()["datos"]["usuario"]
    assert cuerpo["id"] == usuario["id"]
    assert cuerpo["correoElectronico"] == "get@correo.com"
    assert cuerpo["nombreCompleto"] == "Usuario Perfil"
    assert cuerpo["urlFotoPerfil"] == usuario["urlFotoPerfil"]
    assert "contrasenaMd5" not in cuerpo
    assert "claveFotoPerfil" not in cuerpo


def test_get_perfil_usuario_borrado_despues_del_login(client):
    token, usuario = _registrar_y_loguear(client, correo="borrado@correo.com")

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario["id"],))

    respuesta = client.get(RUTA_PERFIL, headers=_auth(token))

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_put_perfil_sin_token_es_rechazado(client):
    respuesta = client.put(RUTA_PERFIL, data={"contrasenaActual": "clave123"})

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_put_perfil_actualiza_nombre(client):
    token, _ = _registrar_y_loguear(client, correo="nombre@correo.com", contrasena="clave123")

    respuesta = client.put(
        RUTA_PERFIL,
        headers=_auth(token),
        data={"contrasenaActual": "clave123", "nombreCompleto": "Nombre Nuevo"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()["datos"]["usuario"]
    assert cuerpo["nombreCompleto"] == "Nombre Nuevo"

    respuesta_get = client.get(RUTA_PERFIL, headers=_auth(token))
    assert respuesta_get.json()["datos"]["usuario"]["nombreCompleto"] == "Nombre Nuevo"


def test_put_perfil_actualiza_foto(client):
    token, usuario_original = _registrar_y_loguear(client, correo="foto@correo.com", contrasena="clave123")

    respuesta = client.put(
        RUTA_PERFIL,
        headers=_auth(token),
        data={"contrasenaActual": "clave123"},
        files={"fotoPerfil": ("nueva.webp", b"contenido-nuevo", "image/webp")},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()["datos"]["usuario"]
    assert cuerpo["urlFotoPerfil"] != usuario_original["urlFotoPerfil"]
    assert cuerpo["urlFotoPerfil"].endswith(".webp")


def test_put_perfil_contrasena_actual_incorrecta(client):
    token, _ = _registrar_y_loguear(client, correo="malaclave@correo.com", contrasena="clave123")

    respuesta = client.put(
        RUTA_PERFIL,
        headers=_auth(token),
        data={"contrasenaActual": "incorrecta", "nombreCompleto": "Otro Nombre"},
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_put_perfil_falta_contrasena_actual(client):
    token, _ = _registrar_y_loguear(client, correo="sinclave@correo.com", contrasena="clave123")

    respuesta = client.put(RUTA_PERFIL, headers=_auth(token), data={"nombreCompleto": "Otro Nombre"})

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ERROR_VALIDACION"


def test_put_perfil_tipo_imagen_no_soportado(client):
    token, _ = _registrar_y_loguear(client, correo="imagenmala@correo.com", contrasena="clave123")

    respuesta = client.put(
        RUTA_PERFIL,
        headers=_auth(token),
        data={"contrasenaActual": "clave123"},
        files={"fotoPerfil": ("archivo.txt", b"no es una imagen", "text/plain")},
    )

    assert respuesta.status_code == 415
    assert respuesta.json()["error"]["codigo"] == "TIPO_CONTENIDO_NO_SOPORTADO"


def test_put_perfil_sin_cambios_no_se_valida(client):
    """Decisión explícita (ver app/perfil/service.py): el diseño original exige
    400 SIN_CAMBIOS_PROPUESTOS si no se envía nombreCompleto ni fotoPerfil,
    pero Node nunca lo implementó — responde 200 sin cambiar nada. Python
    replica ese comportamiento observable real, no el del diseño."""
    token, usuario = _registrar_y_loguear(client, correo="sincambios@correo.com", contrasena="clave123")

    respuesta = client.put(RUTA_PERFIL, headers=_auth(token), data={"contrasenaActual": "clave123"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()["datos"]["usuario"]
    assert cuerpo["nombreCompleto"] == usuario["nombreCompleto"]
    assert cuerpo["urlFotoPerfil"] == usuario["urlFotoPerfil"]


def test_put_perfil_ignora_campos_no_declarados(client):
    """Node usa ValidationPipe con whitelist:true: descarta en silencio
    cualquier campo fuera del DTO (p. ej. correoElectronico) en vez de
    rechazarlo. Python debe comportarse igual."""
    token, usuario = _registrar_y_loguear(client, correo="whitelist@correo.com", contrasena="clave123")

    respuesta = client.put(
        RUTA_PERFIL,
        headers=_auth(token),
        data={
            "contrasenaActual": "clave123",
            "nombreCompleto": "Nombre Whitelist",
            "correoElectronico": "otro@correo.com",
            "id": "999",
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()["datos"]["usuario"]
    assert cuerpo["nombreCompleto"] == "Nombre Whitelist"
    assert cuerpo["correoElectronico"] == usuario["correoElectronico"]
    assert cuerpo["id"] == usuario["id"]
