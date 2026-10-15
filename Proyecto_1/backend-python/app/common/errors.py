"""Esquema común de errores: ``{code, message, requestId, details}``.

Los mensajes por defecto replican los ejemplos de ``docs/api/openapi.yaml``.
Nunca se devuelven trazas, nombres de tablas ni mensajes internos.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("semisocial.errors")

DEFAULT_MESSAGES: dict[str, str] = {
    "VALIDATION_ERROR": "Revise los datos enviados.",
    "UNAUTHENTICATED": "Autenticación requerida.",
    "FORBIDDEN": "No tiene acceso a este recurso.",
    "NOT_FOUND": "Recurso no encontrado.",
    "METHOD_NOT_ALLOWED": "Método no permitido para este recurso.",
    "CONFLICT": "El recurso ya existe.",
    "FILE_TOO_LARGE": "El archivo supera el límite permitido.",
    "UNSUPPORTED_MEDIA_TYPE": "Tipo de contenido no permitido.",
    "FACE_NOT_MATCHED": "No fue posible verificar el rostro.",
    "RATE_LIMITED": "Intente más tarde.",
    "INTERNAL_SERVER_ERROR": "Error interno del servidor.",
    "NOT_IMPLEMENTED": "Funcionalidad pendiente en la API Python.",
    "SERVICE_UNAVAILABLE": "Servicio no disponible.",
}

STATUS_CODES: dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "FACE_NOT_MATCHED",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
    501: "NOT_IMPLEMENTED",
    503: "SERVICE_UNAVAILABLE",
}


class ApiError(Exception):
    """Error de negocio que se serializa con el esquema común."""

    def __init__(
        self,
        status_code: int,
        code: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code or STATUS_CODES.get(status_code, "INTERNAL_SERVER_ERROR")
        self.message = message or DEFAULT_MESSAGES.get(self.code, DEFAULT_MESSAGES["INTERNAL_SERVER_ERROR"])
        self.details = details
        self.headers = headers
        super().__init__(self.code)


class UnauthenticatedError(ApiError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(401, "UNAUTHENTICATED", message, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(ApiError):
    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(403, "FORBIDDEN", message, details)


class ServiceUnavailableError(ApiError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(503, "SERVICE_UNAVAILABLE", message)


class NotImplementedApiError(ApiError):
    """Transitorio y exclusivo de Python (ver docs/api/python.md)."""

    def __init__(self, ticket: str, operation_id: str) -> None:
        super().__init__(501, "NOT_IMPLEMENTED", details={"ticket": ticket, "operationId": operation_id})


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id or str(uuid.uuid4())


def error_body(request_id: str, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "requestId": request_id, "details": details}


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = error_body(get_request_id(request), code, message or DEFAULT_MESSAGES.get(code, ""), details)
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _validation_details(exc: RequestValidationError) -> dict[str, Any]:
    """Resume errores de pydantic sin repetir el valor recibido (podría ser una contraseña)."""
    fields = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ())]
        location = loc[0] if loc else "body"
        name = ".".join(loc[1:]) or location
        fields.append({"in": location, "field": name, "error": err.get("msg", "Valor inválido")})
    return {"fields": fields}


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # El contrato usa 400 VALIDATION_ERROR (no el 422 por defecto de FastAPI).
    return error_response(request, 400, "VALIDATION_ERROR", details=_validation_details(exc))


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = STATUS_CODES.get(exc.status_code, "INTERNAL_SERVER_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR")
    # Se ignora exc.detail: puede contener texto interno de la librería.
    return error_response(request, exc.status_code, code, headers=getattr(exc, "headers", None))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    # Las excepciones no controladas se atrapan en RequestContextMiddleware
    # (app/common/logs.py) para registrar solo información sanitizada.
