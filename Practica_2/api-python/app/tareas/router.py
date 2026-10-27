from fastapi import APIRouter, Response, status

from app.seguridad import UsuarioAutenticado
from app.tareas import service
from app.tareas.schemas import SolicitudEstadoTarea, SolicitudTarea
from app.validaciones import IdRecurso

router = APIRouter(prefix="/api/v1/tasks", tags=["Tareas"])


@router.get("")
def listar_tareas(usuario: UsuarioAutenticado) -> dict:
    return {"exito": True, "datos": service.listar_tareas(usuario.id)}


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_tarea(usuario: UsuarioAutenticado, datos: SolicitudTarea) -> dict:
    return {"exito": True, "datos": service.crear_tarea(usuario.id, datos)}


@router.get("/{taskId}")
def obtener_tarea(usuario: UsuarioAutenticado, taskId: IdRecurso) -> dict:
    return {"exito": True, "datos": service.obtener_tarea(usuario.id, taskId)}


@router.put("/{taskId}")
def editar_tarea(usuario: UsuarioAutenticado, taskId: IdRecurso, datos: SolicitudTarea) -> dict:
    return {"exito": True, "datos": service.editar_tarea(usuario.id, taskId, datos)}


@router.patch("/{taskId}")
def cambiar_estado(usuario: UsuarioAutenticado, taskId: IdRecurso, datos: SolicitudEstadoTarea) -> dict:
    return {"exito": True, "datos": service.cambiar_estado(usuario.id, taskId, datos)}


@router.delete("/{taskId}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tarea(usuario: UsuarioAutenticado, taskId: IdRecurso) -> Response:
    service.eliminar_tarea(usuario.id, taskId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
