from app.database import get_cursor
from tests.conftest import archivo_imagen_de_prueba

RUTA_PELICULAS = "/api/v1/peliculas"
RUTA_REGISTRO = "/api/v1/autenticacion/registro"
RUTA_LOGIN = "/api/v1/autenticacion/inicio-sesion"

ESTADOS_VALIDOS = {"DISPONIBLE", "PROXIMO_ESTRENO"}


def _token(client, correo="galeria@correo.com", contrasena="clave123"):
    client.post(
        RUTA_REGISTRO,
        data={
            "correoElectronico": correo,
            "nombreCompleto": "Usuario Galeria",
            "contrasena": contrasena,
            "confirmacionContrasena": contrasena,
        },
        files=archivo_imagen_de_prueba(),
    )
    respuesta = client.post(RUTA_LOGIN, json={"correoElectronico": correo, "contrasena": contrasena})
    return respuesta.json()["datos"]["token"]


def _cantidad_peliculas_sembradas() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM peliculas")
        return cur.fetchone()["total"]


def test_get_peliculas_sin_token_es_rechazado(client):
    respuesta = client.get(RUTA_PELICULAS)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"


def test_get_peliculas_exitoso(client):
    token = _token(client, correo="galeria1@correo.com")

    respuesta = client.get(RUTA_PELICULAS, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()["datos"]
    assert cuerpo["total"] == _cantidad_peliculas_sembradas()
    assert len(cuerpo["peliculas"]) == cuerpo["total"]

    for pelicula in cuerpo["peliculas"]:
        assert set(pelicula.keys()) == {
            "id",
            "titulo",
            "director",
            "anioEstreno",
            "urlContenido",
            "estado",
            "urlPortada",
        }
        assert pelicula["estado"] in ESTADOS_VALIDOS
        assert pelicula["urlPortada"].startswith("https://")
        assert "Fotos_Peliculas/" in pelicula["urlPortada"]
        assert isinstance(pelicula["anioEstreno"], int)


def test_get_peliculas_ordenadas_por_id_ascendente(client):
    token = _token(client, correo="galeria2@correo.com")

    respuesta = client.get(RUTA_PELICULAS, headers={"Authorization": f"Bearer {token}"})

    ids = [p["id"] for p in respuesta.json()["datos"]["peliculas"]]
    assert ids == sorted(ids)
