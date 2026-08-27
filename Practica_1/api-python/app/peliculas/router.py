"""GET /api/v1/peliculas.

Ruta y protección confirmadas contra api-node/src/peliculas/peliculas.controller.ts
(`@Controller('peliculas')` + `@UseGuards(JwtAuthGuard)` a nivel de
controlador, bajo el prefijo global /api/v1) — el endpoint SÍ requiere
autenticación, a pesar de listar solo el catálogo público de películas.
"""

from fastapi import APIRouter, Depends

from app.peliculas import service
from app.seguridad import UsuarioActual, obtener_usuario_actual

router = APIRouter(prefix="/api/v1/peliculas", tags=["peliculas"])


@router.get("")
def listar_peliculas(usuario_actual: UsuarioActual = Depends(obtener_usuario_actual)) -> dict:
    return {"exito": True, "datos": service.listar_peliculas()}
