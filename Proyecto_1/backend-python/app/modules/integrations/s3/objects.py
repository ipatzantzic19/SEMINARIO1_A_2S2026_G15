"""Comprobación de existencia de objetos con HeadObject.

Según la documentación de HeadObject, un objeto inexistente responde 404 si el
rol tiene ``s3:ListBucket`` y 403 si no lo tiene. El rol backend solo tiene
``ListBucket`` con condición ``s3:prefix`` (no aplica a un HEAD), así que 403
y 404 se tratan igual: "no existe". Otros errores, timeouts o falta de
credenciales → 503. El log registra la operación y el código, nunca la clave.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.common.errors import ServiceUnavailableError

logger = logging.getLogger("semisocial.s3")

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound", "403", "AccessDenied", "Forbidden"}


@dataclass(frozen=True)
class ObjectInfo:
    content_type: str | None
    content_length: int | None


class ImageObjects:
    def __init__(self, bucket: str, client_factory: Callable[[], Any]) -> None:
        self._bucket = bucket
        self._client_factory = client_factory
        self._client: Any = None
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._client_factory()
        return self._client

    def head(self, key: str) -> ObjectInfo | None:
        """Metadatos del objeto, o ``None`` si no existe o no es legible."""
        start = time.perf_counter()
        try:
            response = self._get_client().head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "Unknown"))
            if code in _NOT_FOUND_CODES:
                _log(start, error_type="ObjectNotFound", aws_error_code=code, level=logging.INFO)
                return None
            _log(start, error_type=type(exc).__name__, aws_error_code=code)
            raise ServiceUnavailableError() from None
        except BotoCoreError as exc:
            _log(start, error_type=type(exc).__name__)
            raise ServiceUnavailableError() from None
        _log(start)
        length = response.get("ContentLength")
        return ObjectInfo(
            content_type=response.get("ContentType"),
            content_length=int(length) if length is not None else None,
        )


def _log(start: float, *, error_type: str | None = None, aws_error_code: str | None = None, level: int | None = None) -> None:
    extra: dict[str, Any] = {
        "event": "s3.call",
        "operation": "HeadObject",
        "durationMs": round((time.perf_counter() - start) * 1000, 1),
    }
    if error_type:
        extra["errorType"] = error_type
    if aws_error_code:
        extra["awsErrorCode"] = aws_error_code
    if level is None:
        level = logging.WARNING if error_type else logging.INFO
    logger.log(level, "s3", extra=extra)
