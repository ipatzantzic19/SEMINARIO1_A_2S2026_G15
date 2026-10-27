"""Metadatos de archivos. El binario vive en S3/Blob; aquí solo se guarda la referencia.

Todas las consultas filtran por usuario_id (el del token). DELETE borra solo el
registro en la base, no el objeto del proveedor.
"""

from psycopg import errors as pg_errors

from app import acuerdos, database
from app.archivos.schemas import SolicitudArchivo
from app.errors import ApiError
from app.seguridad import error_token
from app.serializacion import fila_a_json

COLUMNAS_ARCHIVO = (
    "id",
    "usuario_id",
    "nombre_original",
    "tipo_mime",
    "tamano_bytes",
    "proveedor_almacenamiento",
    "clave_objeto",
    "url_objeto",
    "creado_en",
)
_SELECT = ", ".join(COLUMNAS_ARCHIVO)

_SQL_LISTAR = f"""
    SELECT {_SELECT} FROM archivos
    WHERE usuario_id = %s
    ORDER BY creado_en DESC, id DESC
"""

_SQL_REGISTRAR = f"""
    INSERT INTO archivos (
        usuario_id, nombre_original, tipo_mime, tamano_bytes,
        proveedor_almacenamiento, clave_objeto, url_objeto
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING {_SELECT}
"""

_SQL_OBTENER = f"SELECT {_SELECT} FROM archivos WHERE id = %s AND usuario_id = %s"

_SQL_ELIMINAR = "DELETE FROM archivos WHERE id = %s AND usuario_id = %s RETURNING id"


def _archivo_json(fila: dict) -> dict:
    return fila_a_json(fila, COLUMNAS_ARCHIVO)


def _no_encontrado() -> ApiError:
    return ApiError(acuerdos.NO_ENCONTRADO, acuerdos.MENSAJE_ARCHIVO_NO_ENCONTRADO)


def listar_archivos(usuario_id: int) -> dict:
    with database.conexion() as conn:
        filas = conn.execute(_SQL_LISTAR, (usuario_id,)).fetchall()
    archivos = [_archivo_json(fila) for fila in filas]
    return {"archivos": archivos, "total": len(archivos)}


def registrar_archivo(usuario_id: int, datos: SolicitudArchivo) -> dict:
    try:
        with database.conexion() as conn:
            fila = conn.execute(
                _SQL_REGISTRAR,
                (
                    usuario_id,
                    datos.nombreOriginal,
                    datos.tipoMime,
                    datos.tamanoBytes,
                    datos.proveedorAlmacenamiento,
                    datos.claveObjeto,
                    datos.urlObjeto,
                ),
            ).fetchone()
    except pg_errors.ForeignKeyViolation as exc:
        # El token es válido pero su usuario ya no existe.
        raise error_token() from exc
    return {"archivo": _archivo_json(fila)}


def obtener_archivo(usuario_id: int, archivo_id: int) -> dict:
    with database.conexion() as conn:
        fila = conn.execute(_SQL_OBTENER, (archivo_id, usuario_id)).fetchone()
    if fila is None:
        raise _no_encontrado()
    return {"archivo": _archivo_json(fila)}


def eliminar_archivo(usuario_id: int, archivo_id: int) -> None:
    with database.conexion() as conn:
        fila = conn.execute(_SQL_ELIMINAR, (archivo_id, usuario_id)).fetchone()
    if fila is None:
        raise _no_encontrado()
