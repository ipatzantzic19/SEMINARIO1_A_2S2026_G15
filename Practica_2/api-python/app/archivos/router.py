from fastapi import APIRouter, Response, status

from app.archivos import service
from app.archivos.schemas import SolicitudArchivo
from app.seguridad import UsuarioAutenticado
from app.validaciones import IdRecurso

router = APIRouter(prefix="/api/v1/files", tags=["Archivos"])


@router.get("")
def listar_archivos(usuario: UsuarioAutenticado) -> dict:
    return {"exito": True, "datos": service.listar_archivos(usuario.id)}


@router.post("", status_code=status.HTTP_201_CREATED)
def registrar_archivo(usuario: UsuarioAutenticado, datos: SolicitudArchivo) -> dict:
    return {"exito": True, "datos": service.registrar_archivo(usuario.id, datos)}


@router.get("/{fileId}")
def obtener_archivo(usuario: UsuarioAutenticado, fileId: IdRecurso) -> dict:
    return {"exito": True, "datos": service.obtener_archivo(usuario.id, fileId)}


@router.delete("/{fileId}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_archivo(usuario: UsuarioAutenticado, fileId: IdRecurso) -> Response:
    service.eliminar_archivo(usuario.id, fileId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
