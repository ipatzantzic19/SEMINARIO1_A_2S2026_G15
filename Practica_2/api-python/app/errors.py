"""Errores de la API con el sobre común del contrato.

    { "exito": false, "error": { "codigo", "mensaje", "detalles"?: [{ "campo"?, "mensaje" }] } }

Los códigos, estados HTTP y mensajes salen de app/acuerdos.py. Los errores de
validación de pydantic se traducen al español y los 500 nunca exponen trazas,
SQL ni detalles internos.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app import acuerdos
from app.acuerdos import CodigoError

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, error: CodigoError, mensaje: str, detalles: list[dict] | None = None):
        super().__init__(mensaje)
        self.error = error
        self.mensaje = mensaje
        self.detalles = detalles


def detalle(mensaje: str, campo: str | None = None) -> dict:
    resultado: dict = {}
    if campo is not None:
        resultado["campo"] = campo
    resultado["mensaje"] = mensaje
    return resultado


def respuesta_error(error: CodigoError, mensaje: str, detalles: list[dict] | None = None) -> JSONResponse:
    cuerpo: dict = {"codigo": error.codigo, "mensaje": mensaje}
    if detalles:
        cuerpo["detalles"] = detalles
    return JSONResponse(status_code=error.estado_http, content={"exito": False, "error": cuerpo})


def _campo_desde_loc(loc: tuple) -> str | None:
    # FastAPI antepone la fuente ("body", "path", ...); el campo es el último
    # elemento de texto. Las posiciones numéricas (json_invalid) no son campos.
    partes = [parte for parte in loc[1:] if isinstance(parte, str)]
    return partes[-1] if partes else None


def _mensaje_validacion(error: dict, campo: str | None) -> str:
    tipo = error.get("type", "")
    if tipo == "missing" and campo is None:
        return acuerdos.DETALLE_CUERPO_OBLIGATORIO
    if tipo == "string_pattern_mismatch" and campo in acuerdos.MENSAJES_FORMATO_POR_CAMPO:
        return acuerdos.MENSAJES_FORMATO_POR_CAMPO[campo]
    if tipo.startswith("taskflow_"):
        # Errores propios (PydanticCustomError) ya redactados en español.
        return error.get("msg", acuerdos.MENSAJE_VALIDACION_GENERICO)
    plantilla = acuerdos.TRADUCCIONES_VALIDACION.get(tipo)
    if plantilla is None:
        return acuerdos.MENSAJE_VALIDACION_GENERICO
    try:
        return plantilla.format(**(error.get("ctx") or {}))
    except (KeyError, IndexError):
        return acuerdos.MENSAJE_VALIDACION_GENERICO


def traducir_errores_validacion(errores: list[dict]) -> list[dict]:
    detalles = []
    for error in errores:
        campo = _campo_desde_loc(tuple(error.get("loc", ())))
        detalles.append(detalle(_mensaje_validacion(error, campo), campo))
    return detalles


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return respuesta_error(exc.error, exc.mensaje, exc.detalles)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        return respuesta_error(
            acuerdos.ERROR_VALIDACION,
            acuerdos.MENSAJE_VALIDACION,
            traducir_errores_validacion(list(exc.errors())),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Solo errores que genera el propio framework (ruta inexistente, método no permitido...).
        if exc.status_code == 404:
            return respuesta_error(acuerdos.NO_ENCONTRADO, acuerdos.MENSAJE_NO_ENCONTRADO)
        if exc.status_code == 401:
            return respuesta_error(acuerdos.ERROR_AUTENTICACION, acuerdos.MENSAJE_TOKEN_INVALIDO)
        if exc.status_code >= 500:
            return respuesta_error(acuerdos.ERROR_INTERNO, acuerdos.MENSAJE_ERROR_INTERNO)
        error = CodigoError(acuerdos.ERROR_VALIDACION.codigo, exc.status_code)
        return respuesta_error(error, acuerdos.MENSAJE_VALIDACION)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return respuesta_error(acuerdos.ERROR_INTERNO, acuerdos.MENSAJE_ERROR_INTERNO)
