"""Lógica de negocio de GET /peliculas (galería).

Replica api-node/src/peliculas/peliculas.service.ts: `SELECT ... FROM
peliculas ORDER BY id ASC`, serializado con `urlPortada` (no `urlPoster`;
ver nota en el resumen de PRA-14) construida con el mismo patrón que
`urlFotoPerfil` pero sobre el prefijo `Fotos_Peliculas/`.
"""

from app.database import get_cursor
from app.s3_service import get_public_url


def serializar_pelicula(pelicula: dict) -> dict:
    return {
        "id": pelicula["id"],
        "titulo": pelicula["titulo"],
        "director": pelicula["director"],
        "anioEstreno": pelicula["anio_estreno"],
        "urlContenido": pelicula["url_contenido"],
        "estado": pelicula["estado"],
        "urlPortada": get_public_url(pelicula["clave_portada"]),
    }


def listar_peliculas() -> dict:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, titulo, director, anio_estreno, url_contenido, estado, clave_portada "
            "FROM peliculas ORDER BY id ASC"
        )
        peliculas = [serializar_pelicula(fila) for fila in cur.fetchall()]

    return {"peliculas": peliculas, "total": len(peliculas)}
