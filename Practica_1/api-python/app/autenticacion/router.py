"""POST /api/v1/autenticacion/registro y /inicio-sesion.

Rutas exactas tomadas de contracts/openapi.yaml y de la auditoría en
docs/api/node-api-conformance.md,
y de api-node/src/autenticacion/autenticacion.controller.ts
(`@Controller('autenticacion')`, `@Post('registro')`, `@Post('inicio-sesion')`,
con el prefijo global /api/v1). El ticket original mencionaba
"/api/v1/register" y "/api/v1/login" como atajo, pero esas rutas en inglés
no existen en el contrato documentado ni en Node.js — usar esas rutas
rompería la transparencia detrás del balanceador de carga, así que aquí se
usan las rutas reales.
"""

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import ValidationError

from app.autenticacion import service
from app.autenticacion.schemas import InicioSesionRequest, RegistroForm
from app.errors import api_error_validacion, detalles_desde_errores_pydantic

router = APIRouter(prefix="/api/v1/autenticacion", tags=["autenticacion"])


@router.post("/registro", status_code=201)
def registrar(
    correoElectronico: str = Form(...),
    nombreCompleto: str = Form(...),
    contrasena: str = Form(...),
    confirmacionContrasena: str = Form(...),
    fotoPerfil: UploadFile = File(...),
) -> dict:
    # Validación manual (en vez de un modelo Form de FastAPI) para no depender
    # de una versión específica de FastAPI y controlar exactamente el formato
    # de "detalles" del error, igual que el resto del catálogo.
    try:
        dto = RegistroForm(
            correoElectronico=correoElectronico,
            nombreCompleto=nombreCompleto,
            contrasena=contrasena,
            confirmacionContrasena=confirmacionContrasena,
        )
    except ValidationError as exc:
        raise api_error_validacion(detalles_desde_errores_pydantic(exc.errors())) from exc

    contenido = fotoPerfil.file.read()
    nombre_archivo = fotoPerfil.filename or "imagen.jpg"
    usuario = service.registrar(dto, contenido, nombre_archivo, fotoPerfil.content_type)

    return {"exito": True, "datos": {"usuario": usuario}}


@router.post("/inicio-sesion")
def iniciar_sesion(dto: InicioSesionRequest) -> dict:
    datos = service.iniciar_sesion(dto)
    return {"exito": True, "datos": datos}
