"""DetectLabels sobre una imagen de ``Fotos_Publicadas/`` con reintentos.

- Estrategia de Node: ``MaxLabels=20``, ``MinConfidence=80`` y hasta 2 reintentos
  (250 ms y 750 ms) ante throttling o ``InternalServerError``.
- Sin etiquetas calificadas devuelve una lista vacía (no se inventa "general").
- Errores al esquema común sin exponer el mensaje de AWS (``labels.md`` define
  502/422 y códigos ``POST_IMAGE_*``; prevalece la tabla común del OpenAPI):

  =====================================  =====  ==========================================
  AWS                                    HTTP   code / details.reason
  =====================================  =====  ==========================================
  InvalidS3ObjectException               404    NOT_FOUND / IMAGE_NOT_FOUND
  InvalidImageFormatException,           400    VALIDATION_ERROR / IMAGE_UNSUPPORTED
  ImageTooLargeException
  Throttling (tras los reintentos)       429    RATE_LIMITED
  InternalServerError (tras reintentos)  503    SERVICE_UNAVAILABLE
  AccessDenied, credenciales, red, etc.  503    SERVICE_UNAVAILABLE
  =====================================  =====  ==========================================

- Los logs solo registran la operación, la duración, el número de etiquetas y el
  código de error de AWS; nunca la clave de la imagen, el mensaje de AWS ni las
  etiquetas.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.rekognition import MAX_LABELS, MIN_CONFIDENCE
from app.modules.integrations.rekognition.labels import MAX_NAME_CHARS, NormalizedLabel, normalize_label

logger = logging.getLogger("semisocial.rekognition")

RETRY_DELAYS_SECONDS = (0.25, 0.75)

_THROTTLING = {
    "ThrottlingException",
    "ProvisionedThroughputExceededException",
    "TooManyRequestsException",
    "RequestLimitExceeded",
}
_RETRYABLE = _THROTTLING | {"InternalServerError"}
_UNSUPPORTED_IMAGE = {"InvalidImageFormatException", "ImageTooLargeException"}


class LabelDetector:
    """Envuelve el cliente boto3; el cliente se crea en la primera llamada."""

    def __init__(
        self,
        client_factory: Callable[[], Any],
        bucket: str,
        *,
        sleep: Callable[[float], None] = time.sleep,
        delays: tuple[float, ...] = RETRY_DELAYS_SECONDS,
    ) -> None:
        self._client_factory = client_factory
        self._bucket = bucket
        self._sleep = sleep
        self._delays = delays
        self._client: Any = None
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._client_factory()
        return self._client

    def detect(self, image_key: str) -> list[NormalizedLabel]:
        start = time.perf_counter()
        try:
            response = self._call_with_retries(image_key, start)
        except BotoCoreError as exc:
            # Sin credenciales, sin red (timeout, DNS, endpoint) o región inválida.
            _log("aws_unavailable", start, logging.WARNING, error_type=type(exc).__name__)
            raise ServiceUnavailableError() from None
        labels = _collect(response)
        _log("detected", start, logging.INFO, label_count=len(labels))
        return labels

    def _call_with_retries(self, image_key: str, start: float) -> dict[str, Any]:
        client = self._get_client()
        for attempt in range(len(self._delays) + 1):
            try:
                return client.detect_labels(
                    Image={"S3Object": {"Bucket": self._bucket, "Name": image_key}},
                    MaxLabels=MAX_LABELS,
                    MinConfidence=MIN_CONFIDENCE,
                )
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", "Unknown"))
                last_attempt = attempt == len(self._delays)
                if code in _RETRYABLE and not last_attempt:
                    _log("retry", start, logging.WARNING, error_type=type(exc).__name__, aws_error_code=code)
                    self._sleep(self._delays[attempt])
                    continue
                raise self._map_error(exc, code, start) from None
        raise ServiceUnavailableError()  # pragma: no cover - el bucle siempre retorna o lanza

    @staticmethod
    def _map_error(exc: ClientError, code: str, start: float) -> ApiError:
        # Solo el código y el nombre de la excepción: el mensaje de AWS puede
        # incluir ARNs o la clave del objeto.
        level = logging.ERROR if code in ("AccessDeniedException", "UnrecognizedClientException") else logging.WARNING
        _log("aws_error", start, level, error_type=type(exc).__name__, aws_error_code=code)
        if code == "InvalidS3ObjectException":
            return ApiError(404, "NOT_FOUND", "No se encontró la imagen de la publicación.", {"reason": "IMAGE_NOT_FOUND"})
        if code in _UNSUPPORTED_IMAGE:
            return ApiError(
                400, "VALIDATION_ERROR", "La imagen no tiene un formato válido para analizarla.", {"reason": "IMAGE_UNSUPPORTED"}
            )
        if code in _THROTTLING:
            return ApiError(429, "RATE_LIMITED")
        # AccessDenied, credenciales vencidas, InternalServerError persistente, etc.
        return ServiceUnavailableError()


def _collect(response: dict[str, Any]) -> list[NormalizedLabel]:
    """Descarta etiquetas sin nombre o bajo el umbral y deduplica por nombre normalizado."""
    best: dict[str, NormalizedLabel] = {}
    for item in response.get("Labels") or []:
        name = item.get("Name")
        confidence = item.get("Confidence")
        if not name or confidence is None or float(confidence) < MIN_CONFIDENCE:
            continue
        label = normalize_label(name, confidence)
        if not label.name or "\x00" in label.name:
            continue
        label = NormalizedLabel(label.name, label.confidence, label.source_name[:MAX_NAME_CHARS])
        current = best.get(label.name)
        if current is None or label.confidence > current.confidence:
            best[label.name] = label
    ordered = sorted(best.values(), key=lambda label: (-label.confidence, label.name))
    return ordered[:MAX_LABELS]


def _log(
    event: str,
    start: float,
    level: int,
    *,
    error_type: str | None = None,
    aws_error_code: str | None = None,
    label_count: int | None = None,
) -> None:
    extra: dict[str, Any] = {
        "event": f"rekognition.{event}",
        "durationMs": round((time.perf_counter() - start) * 1000, 1),
    }
    if error_type:
        extra["errorType"] = error_type
    if aws_error_code:
        extra["awsErrorCode"] = aws_error_code
    if label_count is not None:
        extra["labelCount"] = label_count
    logger.log(level, "rekognition", extra=extra)
