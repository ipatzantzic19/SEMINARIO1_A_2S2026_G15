from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import get_cursor
from app.main import app as fastapi_app
from app.playlist import service as playlist_service
from tests.conftest import archivo_imagen_de_prueba

RUTA_PLAYLIST = "/api/v1/lista-reproduccion"
RUTA_REGISTRO = "/api/v1/autenticacion/registro"
RUTA_LOGIN = "/api/v1/autenticacion/inicio-sesion"


def _token(client, correo="playlist@correo.com", contrasena="clave123"):
    client.post(
        RUTA_REGISTRO,
        data={
            "correoElectronico": correo,
            "nombreCompleto": "Usuario Playlist",
            "contrasena": contrasena,
            "confirmacionContrasena": contrasena,
        },
        files=archivo_imagen_de_prueba(),
    )
    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": correo, "contrasena": contrasena})
    datos = respuesta.json()["datos"]
    return datos["token"], datos["usuario"]["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _pelicula_id_por_estado(estado: str) -> int:
    with get_cursor() as cur:
        cur.execute("SELECT id FROM peliculas WHERE estado = %s ORDER BY id LIMIT 1", (estado,))
        return cur.fetchone()["id"]


def test_get_playlist_sin_token_es_rechazado(client):
    respuesta = client.get(RUTA_PLAYLIST)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_get_playlist_vacia(client):
    token, _ = _token(client, correo="vacia@correo.com")

    respuesta = client.get(RUTA_PLAYLIST, headers=_auth(token))

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"] == {"peliculas": [], "total": 0}


def test_post_playlist_pelicula_disponible_exitoso(client):
    token, _ = _token(client, correo="agregar@correo.com")
    pelicula_id = _pelicula_id_por_estado("DISPONIBLE")

    respuesta = client.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    assert respuesta.status_code == 201
    pelicula = respuesta.json()["datos"]["pelicula"]
    assert pelicula["id"] == pelicula_id
    assert pelicula["estado"] == "DISPONIBLE"
    assert "agregadoEn" in pelicula
    assert pelicula["agregadoEn"].endswith("Z")


def test_post_playlist_pelicula_no_encontrada(client):
    token, _ = _token(client, correo="noencontrada@correo.com")

    respuesta = client.post(f"{RUTA_PLAYLIST}/999999", headers=_auth(token))

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_post_playlist_pelicula_no_disponible(client):
    token, _ = _token(client, correo="nodisponible@correo.com")
    pelicula_id = _pelicula_id_por_estado("PROXIMO_ESTRENO")

    respuesta = client.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["error"]["codigo"] == "ERROR_VALIDACION"
    assert cuerpo["error"]["mensaje"] == "No se puede agregar a la lista una película que no esté disponible."


def test_post_playlist_pelicula_duplicada(client):
    token, _ = _token(client, correo="duplicada@correo.com")
    pelicula_id = _pelicula_id_por_estado("DISPONIBLE")

    client.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))
    respuesta = client.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "CONFLICTO"


def test_post_playlist_id_no_numerico(client):
    token, _ = _token(client, correo="idinvalido@correo.com")

    respuesta = client.post(f"{RUTA_PLAYLIST}/no-es-un-id", headers=_auth(token))

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ERROR_VALIDACION"


def test_get_playlist_ordenada_por_agregado_en_descendente(client):
    token, usuario_id = _token(client, correo="orden@correo.com")
    disponibles = []
    with get_cursor() as cur:
        cur.execute("SELECT id FROM peliculas WHERE estado = 'DISPONIBLE' ORDER BY id")
        disponibles = [fila["id"] for fila in cur.fetchall()]
    assert len(disponibles) >= 2, "el seed debe tener al menos 2 películas DISPONIBLE"
    mas_antigua, mas_reciente = disponibles[0], disponibles[1]

    ahora = datetime.now(timezone.utc)
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO lista_reproduccion (usuario_id, pelicula_id, agregado_en) VALUES (%s, %s, %s)",
            (usuario_id, mas_antigua, ahora - timedelta(hours=1)),
        )
        cur.execute(
            "INSERT INTO lista_reproduccion (usuario_id, pelicula_id, agregado_en) VALUES (%s, %s, %s)",
            (usuario_id, mas_reciente, ahora),
        )

    respuesta = client.get(RUTA_PLAYLIST, headers=_auth(token))

    assert respuesta.status_code == 200
    ids_en_orden = [p["id"] for p in respuesta.json()["datos"]["peliculas"]]
    assert ids_en_orden == [mas_reciente, mas_antigua]


def test_delete_playlist_exitoso(client):
    token, _ = _token(client, correo="eliminar@correo.com")
    pelicula_id = _pelicula_id_por_estado("DISPONIBLE")
    client.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    respuesta = client.delete(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"] == {"peliculaId": pelicula_id, "eliminado": True}

    respuesta_lista = client.get(RUTA_PLAYLIST, headers=_auth(token))
    assert respuesta_lista.json()["datos"]["total"] == 0


def test_delete_playlist_no_esta_en_lista(client):
    token, _ = _token(client, correo="noestaenlista@correo.com")
    pelicula_id = _pelicula_id_por_estado("DISPONIBLE")

    respuesta = client.delete(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_delete_playlist_no_elimina_la_pelicula_del_catalogo(client):
    token, _ = _token(client, correo="noeliminacatalogo@correo.com")
    pelicula_id = _pelicula_id_por_estado("DISPONIBLE")
    client.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    client.delete(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM peliculas WHERE id = %s", (pelicula_id,))
        assert cur.fetchone() is not None


def test_p0001_del_trigger_no_se_filtra_al_cliente(client, monkeypatch):
    """Fuerza el escenario que el trigger `trg_lista_validar_pelicula_disponible`
    (database/schema.sql:100-127) está pensado para atrapar: el guard de
    aplicación (`_esta_disponible`) se salta, así que el INSERT llega
    directo a Postgres para una película PROXIMO_ESTRENO y el trigger lanza
    `PELICULA_NO_DISPONIBLE` con ERRCODE P0001. Confirma que el cliente
    recibe el mismo 500 ERROR_INTERNO sano del resto del catálogo (vía el
    manejador genérico de app/errors.py), nunca el mensaje crudo de
    Postgres ni una traza.

    Usa un TestClient aparte con `raise_server_exceptions=False`: Starlette
    reenvía la excepción no manejada al llamador de todas formas después de
    que `ServerErrorMiddleware` ya armó y envió la respuesta 500 (así el
    servidor ASGI real puede loguearla) — el cliente HTTP real nunca ve esa
    excepción, solo el body sano, pero el `client` de sesión (con el valor
    por defecto `raise_server_exceptions=True`) sí la relanzaría en el test."""
    monkeypatch.setattr(playlist_service, "_esta_disponible", lambda pelicula: True)

    token, _ = _token(client, correo="p0001@correo.com")
    pelicula_id = _pelicula_id_por_estado("PROXIMO_ESTRENO")

    cliente_tolerante = TestClient(fastapi_app, raise_server_exceptions=False)
    respuesta = cliente_tolerante.post(f"{RUTA_PLAYLIST}/{pelicula_id}", headers=_auth(token))

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["error"]["codigo"] == "ERROR_INTERNO"
    assert cuerpo["error"]["mensaje"] == "Error inesperado en el servidor."
    assert "P0001" not in respuesta.text
    assert "PELICULA_NO_DISPONIBLE" not in respuesta.text
    assert "psycopg2" not in respuesta.text.lower()

    with get_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM lista_reproduccion WHERE pelicula_id = %s",
            (pelicula_id,),
        )
        assert cur.fetchone() is None, "el INSERT fallido no debe haber dejado ninguna fila"
