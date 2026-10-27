"""CRUD de tareas. Todas las consultas filtran por usuario_id (el del token)."""

from psycopg import errors as pg_errors

from app import acuerdos, database
from app.errors import ApiError
from app.seguridad import error_token
from app.serializacion import fila_a_json
from app.tareas.schemas import SolicitudEstadoTarea, SolicitudTarea

COLUMNAS_TAREA = (
    "id",
    "usuario_id",
    "titulo",
    "descripcion",
    "fecha_creacion",
    "completada",
    "fecha_completada",
    "actualizado_en",
)
_SELECT = ", ".join(COLUMNAS_TAREA)

_SQL_LISTAR = f"""
    SELECT {_SELECT} FROM tareas
    WHERE usuario_id = %s
    ORDER BY fecha_creacion DESC, id DESC
"""

_SQL_CREAR = f"""
    INSERT INTO tareas (usuario_id, titulo, descripcion, fecha_creacion)
    VALUES (%s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP))
    RETURNING {_SELECT}
"""

_SQL_OBTENER = f"SELECT {_SELECT} FROM tareas WHERE id = %s AND usuario_id = %s"

_SQL_EDITAR = f"""
    UPDATE tareas SET titulo = %s, descripcion = %s
    WHERE id = %s AND usuario_id = %s
    RETURNING {_SELECT}
"""

# Solo se actualiza si el estado cambia. Si ya tenía ese valor, la segunda parte
# devuelve la fila intacta (misma fechaCompletada y actualizadoEn): PATCH idempotente.
_SQL_CAMBIAR_ESTADO = f"""
    WITH cambiada AS (
        UPDATE tareas
        SET completada = %(completada)s,
            fecha_completada = CASE WHEN %(completada)s THEN CURRENT_TIMESTAMP ELSE NULL END
        WHERE id = %(id)s AND usuario_id = %(usuario_id)s
          AND completada IS DISTINCT FROM %(completada)s
        RETURNING {_SELECT}
    )
    SELECT {_SELECT} FROM cambiada
    UNION ALL
    SELECT {_SELECT} FROM tareas
    WHERE id = %(id)s AND usuario_id = %(usuario_id)s
      AND NOT EXISTS (SELECT 1 FROM cambiada)
"""

_SQL_ELIMINAR = "DELETE FROM tareas WHERE id = %s AND usuario_id = %s RETURNING id"


def _tarea_json(fila: dict) -> dict:
    return fila_a_json(fila, COLUMNAS_TAREA)


def _no_encontrada() -> ApiError:
    return ApiError(acuerdos.NO_ENCONTRADO, acuerdos.MENSAJE_TAREA_NO_ENCONTRADA)


def listar_tareas(usuario_id: int) -> dict:
    with database.conexion() as conn:
        filas = conn.execute(_SQL_LISTAR, (usuario_id,)).fetchall()
    tareas = [_tarea_json(fila) for fila in filas]
    return {"tareas": tareas, "total": len(tareas)}


def crear_tarea(usuario_id: int, datos: SolicitudTarea) -> dict:
    try:
        with database.conexion() as conn:
            fila = conn.execute(
                _SQL_CREAR, (usuario_id, datos.titulo, datos.descripcion, datos.fechaCreacion)
            ).fetchone()
    except pg_errors.ForeignKeyViolation as exc:
        # El token es válido pero su usuario ya no existe.
        raise error_token() from exc
    return {"tarea": _tarea_json(fila)}


def obtener_tarea(usuario_id: int, tarea_id: int) -> dict:
    with database.conexion() as conn:
        fila = conn.execute(_SQL_OBTENER, (tarea_id, usuario_id)).fetchone()
    if fila is None:
        raise _no_encontrada()
    return {"tarea": _tarea_json(fila)}


def editar_tarea(usuario_id: int, tarea_id: int, datos: SolicitudTarea) -> dict:
    # datos.fechaCreacion se ignora a propósito: PUT solo modifica título y descripción.
    with database.conexion() as conn:
        fila = conn.execute(_SQL_EDITAR, (datos.titulo, datos.descripcion, tarea_id, usuario_id)).fetchone()
    if fila is None:
        raise _no_encontrada()
    return {"tarea": _tarea_json(fila)}


def cambiar_estado(usuario_id: int, tarea_id: int, datos: SolicitudEstadoTarea) -> dict:
    with database.conexion() as conn:
        fila = conn.execute(
            _SQL_CAMBIAR_ESTADO,
            {"completada": datos.completada, "id": tarea_id, "usuario_id": usuario_id},
        ).fetchone()
    if fila is None:
        raise _no_encontrada()
    return {"tarea": _tarea_json(fila)}


def eliminar_tarea(usuario_id: int, tarea_id: int) -> None:
    with database.conexion() as conn:
        fila = conn.execute(_SQL_ELIMINAR, (tarea_id, usuario_id)).fetchone()
    if fila is None:
        raise _no_encontrada()
