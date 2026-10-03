"""Traduce entre azure.functions y el servicio, con red de seguridad para el 500."""

import logging

import azure.functions as func

from . import respuestas, servicio

logger = logging.getLogger(__name__)


def atender(req: func.HttpRequest, ruta: str) -> func.HttpResponse:
    try:
        respuesta = servicio.procesar(
            ruta,
            req.get_body() or b"",
            req.headers.get("content-type"),
            req.headers.get("authorization"),
        )
    except Exception as exc:
        # No se registra el mensaje: podría contener datos de la petición.
        logger.error("Error no controlado en %s: %s", ruta, type(exc).__name__)
        respuesta = respuestas.error_interno()
    return func.HttpResponse(
        respuesta.json(),
        status_code=respuesta.estado_http,
        headers={"Content-Type": "application/json"},
    )
