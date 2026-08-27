"""GET /api/v1/perfil y PUT /api/v1/perfil.

Ruta exacta tomada de docs/pra-1/CONTRATO_API.md y confirmada en
api-node/src/perfil/perfil.controller.ts (`@Controller('perfil')` bajo el
prefijo global /api/v1) — aquí no hay divergencia entre diseño y código real.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import ValidationError

from app.errors import api_error_validacion, detalles_desde_errores_pydantic
from app.perfil import service
from app.perfil.schemas import ActualizarPerfilForm
from app.seguridad import UsuarioActual, obtener_usuario_actual

router = APIRouter(prefix="/api/v1/perfil", tags=["perfil"])


@router.get("")
def consultar_perfil(usuario_actual: UsuarioActual = Depends(obtener_usuario_actual)) -> dict:
    usuario = service.consultar_perfil(usuario_actual.usuario_id)
    return {"exito": True, "datos": {"usuario": usuario}}


@router.put("")
def actualizar_perfil(
    contrasenaActual: str = Form(...),
    nombreCompleto: str | None = Form(default=None),
    fotoPerfil: UploadFile | None = File(default=None),
    usuario_actual: UsuarioActual = Depends(obtener_usuario_actual),
) -> dict:
    try:
        dto = ActualizarPerfilForm(contrasenaActual=contrasenaActual, nombreCompleto=nombreCompleto)
    except ValidationError as exc:
        raise api_error_validacion(detalles_desde_errores_pydantic(exc.errors())) from exc

    contenido_imagen = None
    nombre_archivo = None
    content_type = None
    if fotoPerfil is not None and fotoPerfil.filename:
        contenido_imagen = fotoPerfil.file.read()
        nombre_archivo = fotoPerfil.filename
        content_type = fotoPerfil.content_type

    usuario = service.actualizar_perfil(
        usuario_actual.usuario_id, dto, contenido_imagen, nombre_archivo, content_type
    )
    return {"exito": True, "datos": {"usuario": usuario}}
