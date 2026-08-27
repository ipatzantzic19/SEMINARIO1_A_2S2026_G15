"""Lógica de negocio de /lista-reproduccion.

Replica el comportamiento REAL de api-node/src/playlist/playlist.service.ts,
verificado en vivo durante la investigación de PRA-14 (Node local contra el
mismo Postgres de Docker que usa esta suite):

- `agregar_pelicula_a_lista` hace su propio `SELECT estado` antes de
  cualquier `INSERT` — igual que Node — y NO depende del trigger
  `trg_lista_validar_pelicula_disponible` (database/schema.sql:100-127)
  para los casos de negocio (película inexistente / no disponible). Ese
  trigger sigue existiendo como red de seguridad adicional a nivel de
  base, pero no es la fuente de los códigos HTTP que debe igualar Python.
- Película inexistente -> 404 NO_ENCONTRADO.
- Película existe pero no está 'DISPONIBLE' -> 400 ERROR_VALIDACION con el
  mensaje verificado en vivo contra Node: "No se puede agregar a la lista
  una película que no esté disponible." (api-node/src/playlist/playlist.service.ts:101-105).
- Ya está en la lista -> 409 CONFLICTO.

Decisión explícita sobre el P0001 del trigger: si por algún motivo (p. ej.
una condición de carrera entre el SELECT y el INSERT) el trigger se
disparara igual, NO se agrega aquí un `except psycopg2.Error` dedicado que
lo traduzca a 500 — el manejador genérico `@app.exception_handler(Exception)`
en app/errors.py YA convierte cualquier excepción no capturada en el mismo
`500 ERROR_INTERNO` sano, sin exponer el mensaje crudo de Postgres.
Agregar un `try/except` aquí que haga exactamente lo mismo sería duplicar
esa lógica. `tests/test_playlist.py::test_p0001_del_trigger_no_se_filtra_al_cliente`
fuerza ese escenario (monkeypatch de `_esta_disponible`) para confirmarlo
en vivo contra la app real.
"""

from datetime import timezone

from app.database import get_cursor
from app.errors import ApiError
from app.peliculas.service import serializar_pelicula


def _buscar_pelicula(pelicula_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, titulo, director, anio_estreno, url_contenido, estado, clave_portada "
            "FROM peliculas WHERE id = %s",
            (pelicula_id,),
        )
        return cur.fetchone()


def _esta_disponible(pelicula: dict) -> bool:
    return pelicula["estado"] == "DISPONIBLE"


def _ya_esta_en_lista(usuario_id: int, pelicula_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM lista_reproduccion WHERE usuario_id = %s AND pelicula_id = %s",
            (usuario_id, pelicula_id),
        )
        return cur.fetchone() is not None


def consultar_lista(usuario_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.titulo, p.director, p.anio_estreno, p.url_contenido, p.estado,
                   p.clave_portada, lr.agregado_en
            FROM lista_reproduccion lr
            INNER JOIN peliculas p ON lr.pelicula_id = p.id
            WHERE lr.usuario_id = %s
            ORDER BY lr.agregado_en DESC
            """,
            (usuario_id,),
        )
        filas = cur.fetchall()

    peliculas = []
    for fila in filas:
        pelicula = serializar_pelicula(fila)
        pelicula["agregadoEn"] = _formato_iso_utc(fila["agregado_en"])
        peliculas.append(pelicula)

    return {"peliculas": peliculas, "total": len(peliculas)}


def agregar_pelicula_a_lista(usuario_id: int, pelicula_id: int) -> dict:
    pelicula = _buscar_pelicula(pelicula_id)
    if pelicula is None:
        raise ApiError(404, "NO_ENCONTRADO", "Película no encontrada.")

    if not _esta_disponible(pelicula):
        raise ApiError(
            400, "ERROR_VALIDACION", "No se puede agregar a la lista una película que no esté disponible."
        )

    if _ya_esta_en_lista(usuario_id, pelicula_id):
        raise ApiError(409, "CONFLICTO", "La película ya se encuentra en tu lista de reproducción.")

    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO lista_reproduccion (usuario_id, pelicula_id) VALUES (%s, %s) RETURNING agregado_en",
            (usuario_id, pelicula_id),
        )
        agregado_en = cur.fetchone()["agregado_en"]

    resultado = serializar_pelicula(pelicula)
    resultado["agregadoEn"] = _formato_iso_utc(agregado_en)
    return {"pelicula": resultado}


def eliminar_pelicula_de_lista(usuario_id: int, pelicula_id: int) -> dict:
    if not _ya_esta_en_lista(usuario_id, pelicula_id):
        raise ApiError(404, "NO_ENCONTRADO", "La película no se encuentra en tu lista de reproducción.")

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM lista_reproduccion WHERE usuario_id = %s AND pelicula_id = %s",
            (usuario_id, pelicula_id),
        )

    return {"peliculaId": pelicula_id, "eliminado": True}


def _formato_iso_utc(momento) -> str:
    return momento.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
