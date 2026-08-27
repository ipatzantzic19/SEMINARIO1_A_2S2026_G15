"""GET /salud — sin prefijo /api/v1, igual que api-node/src/salud/salud.controller.ts,
para que el Load Balancer lo use como health check."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/salud")
def consultar_salud() -> dict:
    return {
        "exito": True,
        "datos": {
            "estado": "ok",
            "servicio": "cloudcinema-api",
            "implementacion": "python",
        },
    }
