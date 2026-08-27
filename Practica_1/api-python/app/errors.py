"""Manejo de errores.

Sigue el mismo sobre `{ "exito": false, "error": { "codigo", "mensaje",
"detalles"? } }` que Node.js, y replica su comportamiento REAL (no el
catálogo fino de contracts/openapi.yaml): el
`codigo` se decide por caso de negocio explícito (CONFLICTO,
ERROR_AUTENTICACION, ERROR_VALIDACION, TIPO_CONTENIDO_NO_SOPORTADO,
ERROR_INTERNO), igual que los códigos que realmente devuelve
api-node/src/common/filters/http-exception.filter.ts hoy, documentado en
docs/api/node-api-conformance.md. Los 500 nunca exponen trazas, SQL ni detalles de AWS.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, codigo: str, mensaje: str, detalles: list | None = None):
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles
        super().__init__(mensaje)


def _cuerpo_error(codigo: str, mensaje: str, detalles: list | None = None) -> dict:
    error: dict = {"codigo": codigo, "mensaje": mensaje}
    if detalles:
        error["detalles"] = detalles
    return {"exito": False, "error": error}


def detalles_desde_errores_pydantic(errores: list[dict]) -> list[dict]:
    detalles = []
    for err in errores:
        loc = err.get("loc", ())
        campo = loc[-1] if loc else None
        detalles.append({"campo": campo, "mensaje": err.get("msg", "Valor inválido.")})
    return detalles


def api_error_validacion(detalles: list[dict] | None = None) -> ApiError:
    return ApiError(400, "ERROR_VALIDACION", "Los datos enviados no son válidos.", detalles=detalles)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_cuerpo_error(exc.codigo, exc.mensaje, exc.detalles))

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        detalles = detalles_desde_errores_pydantic(exc.errors())
        return JSONResponse(
            status_code=400,
            content=_cuerpo_error("ERROR_VALIDACION", "Los datos enviados no son válidos.", detalles),
        )

    @app.exception_handler(ValidationError)
    async def _handle_pydantic_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        detalles = detalles_desde_errores_pydantic(exc.errors())
        return JSONResponse(
            status_code=400,
            content=_cuerpo_error("ERROR_VALIDACION", "Los datos enviados no son válidos.", detalles),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Solo cubre errores que FastAPI/Starlette generan por sí mismos (p. ej. ruta inexistente).
        codigo = "ERROR_INTERNO" if exc.status_code >= 500 else "ERROR_SOLICITUD"
        return JSONResponse(status_code=exc.status_code, content=_cuerpo_error(codigo, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Nunca exponer trazas, SQL ni mensajes internos de AWS, tal como exige el contrato.
        return JSONResponse(status_code=500, content=_cuerpo_error("ERROR_INTERNO", "Error inesperado en el servidor."))
