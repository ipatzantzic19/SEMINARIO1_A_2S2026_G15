"""GET/POST/DELETE /api/v1/lista-reproduccion[/{peliculaId}].

Rutas y protección confirmadas contra api-node/src/playlist/playlist.controller.ts
(`@Controller('lista-reproduccion')` + `@UseGuards(JwtAuthGuard)` a nivel de
controlador) y contracts/openapi.yaml, bajo el prefijo global /api/v1.

`pelicula_id: int` como parámetro de ruta: si no es parseable como entero,
FastAPI levanta `RequestValidationError`, que app/errors.py ya traduce a
`400 ERROR_VALIDACION` — igual que `ParseIntPipe` + el filtro de Node. Un
entero negativo o cero se acepta igual que en Node (su `ParseIntPipe` no
los rechaza) y simplemente no encuentra película -> 404.
"""

from fastapi import APIRouter, Depends

from app.playlist import service
from app.seguridad import UsuarioActual, obtener_usuario_actual

router = APIRouter(prefix="/api/v1/lista-reproduccion", tags=["lista-reproduccion"])


@router.get("")
def consultar_lista(usuario_actual: UsuarioActual = Depends(obtener_usuario_actual)) -> dict:
    return {"exito": True, "datos": service.consultar_lista(usuario_actual.usuario_id)}


@router.post("/{pelicula_id}", status_code=201)
def agregar_pelicula(
    pelicula_id: int,
    usuario_actual: UsuarioActual = Depends(obtener_usuario_actual),
) -> dict:
    datos = service.agregar_pelicula_a_lista(usuario_actual.usuario_id, pelicula_id)
    return {"exito": True, "datos": datos}


@router.delete("/{pelicula_id}")
def eliminar_pelicula(
    pelicula_id: int,
    usuario_actual: UsuarioActual = Depends(obtener_usuario_actual),
) -> dict:
    datos = service.eliminar_pelicula_de_lista(usuario_actual.usuario_id, pelicula_id)
    return {"exito": True, "datos": datos}
