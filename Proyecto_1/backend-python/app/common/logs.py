"""Logging estructurado y sanitizado + contexto de solicitud (requestId).

Política: nunca registrar cuerpos, headers ``Authorization``, query strings,
tokens, contraseñas, imágenes ni secretos. El filtro de redacción es una
segunda línea de defensa; la primera es no pasar esos datos al logger.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.errors import error_body

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), "[REDACTED_JWT]"),
    (re.compile(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+"), "[REDACTED_DATA_URI]"),
    (
        re.compile(
            r"(?i)([\"']?(?:password|currentPassword|newPassword|secret|token|accessToken|idToken|"
            r"refreshToken|uploadToken|authorization|session)[\"']?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,}&]+)"
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"(?i)(postgres(?:ql)?://[^:/\s]+:)[^@\s]+@"), r"\1[REDACTED]@"),
    (re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"), "[REDACTED_BLOB]"),
)


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RedactionFilter(logging.Filter):
    """Reescribe el mensaje final del registro aplicando ``redact``."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - formato inválido
            message = str(record.msg)
        record.msg = redact(message)
        record.args = None
        if record.exc_info:
            # Solo tipo y ubicación de frames: ni mensaje de la excepción ni
            # líneas de código (cualquiera de los dos puede traer datos).
            exc_type, _, tb = record.exc_info
            frames = "".join(
                f'  File "{f.filename}", line {f.lineno}, in {f.name}\n' for f in traceback.extract_tb(tb)
            )
            record.exc_text = redact(f"{exc_type.__name__ if exc_type else 'Exception'}\n{frames}")
            record.exc_info = None
        return True


class JsonFormatter(logging.Formatter):
    _EXTRA_FIELDS = (
        "method",
        "path",
        "status",
        "durationMs",
        "errorType",
        "event",
        "sourceLanguage",
        "targetLanguage",
        "chars",
        "awsErrorCode",
        "intentName",
        "intentState",
        "messageCount",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["requestId"] = request_id
        for name in self._EXTRA_FIELDS:
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        if record.exc_text:
            payload["exc"] = record.exc_text
        return json.dumps(payload, ensure_ascii=False)


def build_handler(stream: Any = None) -> logging.Handler:
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())
    return handler


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(build_handler())
    root.setLevel(level)
    # uvicorn: sin access log propio (incluye query strings); errores al root.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    """Asigna requestId, registra acceso sanitizado y convierte errores no
    controlados en 500 con el esquema común (sin filtrar el mensaje)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("semisocial.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = incoming if incoming and _REQUEST_ID_RE.match(incoming) else str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        status_holder = {"status": 500, "started": False}
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                status_holder["started"] = True
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:  # noqa: BLE001 - frontera de la aplicación
            self.logger.error(
                "unhandled_exception",
                exc_info=exc,
                extra={"event": "unhandled_exception", "errorType": type(exc).__name__},
            )
            if not status_holder["started"]:
                body = json.dumps(
                    error_body(request_id, "INTERNAL_SERVER_ERROR", "Error interno del servidor.")
                ).encode()
                await send_wrapper(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send_wrapper({"type": "http.response.body", "body": body})
        finally:
            # Solo método, ruta sin query string, estado y duración.
            self.logger.info(
                "request",
                extra={
                    "event": "request",
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status_holder["status"],
                    "durationMs": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(token)
