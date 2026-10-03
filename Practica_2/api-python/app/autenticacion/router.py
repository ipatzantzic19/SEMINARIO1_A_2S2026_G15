from fastapi import APIRouter, status

from app.autenticacion import service
from app.autenticacion.schemas import SolicitudInicioSesion, SolicitudRegistro

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def registrar_usuario(datos: SolicitudRegistro) -> dict:
    return {"exito": True, "datos": service.registrar_usuario(datos)}


@router.post("/login")
def iniciar_sesion(datos: SolicitudInicioSesion) -> dict:
    return {"exito": True, "datos": service.iniciar_sesion(datos)}
