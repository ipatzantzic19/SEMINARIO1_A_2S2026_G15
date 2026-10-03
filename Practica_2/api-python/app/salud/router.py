from fastapi import APIRouter

from app import acuerdos, database
from app.errors import ApiError

router = APIRouter(tags=["Salud"])


@router.get("/health")
def consultar_salud() -> dict:
    if not database.verificar_conexion(acuerdos.SALUD_TIMEOUT_SEGUNDOS):
        raise ApiError(acuerdos.BD_NO_DISPONIBLE, acuerdos.MENSAJE_BD_NO_DISPONIBLE)
    return {
        "exito": True,
        "datos": {
            "estado": "ok",
            "servicio": acuerdos.SERVICIO,
            "implementacion": acuerdos.IMPLEMENTACION,
        },
    }
