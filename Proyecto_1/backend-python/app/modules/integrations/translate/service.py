"""Traducción bajo demanda con Amazon Translate (TranslateText).

- No lee ni escribe RDS: recibe el texto que la UI ya muestra y devuelve la
  traducción. El texto original de posts y comentarios nunca se modifica.
- Los errores de AWS se convierten al esquema común sin exponer su mensaje.
- Los logs solo registran idiomas, longitud, duración y el código de error de
  AWS; nunca el texto ni la traducción.

Referencias y decisiones: docs/api/translation.md.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.common.errors import ApiError, ServiceUnavailableError

logger = logging.getLogger("semisocial.translate")

SUPPORTED_TARGETS = ("es", "en", "fr", "de")
AUTO = "auto"
MAX_TEXT_CHARS = 5000  # openapi.yaml
MAX_TEXT_BYTES = 10000  # TranslateText, bytes UTF-8 por solicitud

_THROTTLING = {"ThrottlingException", "TooManyRequestsException", "LimitExceededException", "RequestLimitExceeded"}

# Errores de la solicitud que AWS rechaza: 400 con un motivo estable.
_BAD_REQUEST: dict[str, tuple[str, str]] = {
    "DetectedLanguageLowConfidenceException": (
        "LANGUAGE_DETECTION_LOW_CONFIDENCE",
        "No fue posible detectar el idioma del texto. Indique sourceLanguage.",
    ),
    "UnsupportedLanguagePairException": (
        "UNSUPPORTED_LANGUAGE_PAIR",
        "No es posible traducir entre esos idiomas.",
    ),
    "TextSizeLimitExceededException": (
        "TEXT_TOO_LARGE",
        "El texto supera el tamaño máximo para traducir.",
    ),
    "InvalidRequestException": (
        "INVALID_TRANSLATION_REQUEST",
        "No fue posible traducir el texto enviado.",
    ),
}


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str
    source_language: str
    target_language: str


class TranslationService:
    """Envuelve el cliente boto3; el cliente se crea en la primera llamada."""

    def __init__(self, client_factory: Callable[[], Any]) -> None:
        self._client_factory = client_factory
        self._client: Any = None
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._client_factory()
        return self._client

    def translate(self, text: str, source_language: str, target_language: str) -> TranslationResult:
        # Origen explícito igual al destino: no hay nada que traducir.
        if source_language == target_language:
            self._log("same_language", source_language, target_language, len(text), 0.0)
            return TranslationResult(text, source_language, target_language)

        start = time.perf_counter()
        try:
            response = self._get_client().translate_text(
                Text=text,
                SourceLanguageCode=source_language,
                TargetLanguageCode=target_language,
            )
        except ClientError as exc:
            return self._handle_client_error(exc, text, source_language, target_language, start)
        except BotoCoreError as exc:
            # Sin credenciales, sin red (timeout, DNS, endpoint) o región inválida.
            self._log("aws_unavailable", source_language, target_language, len(text), start, type(exc).__name__)
            raise _with_aws_cause(ServiceUnavailableError(), None, type(exc).__name__) from None

        detected = response.get("SourceLanguageCode") or source_language
        self._log("translated", detected, target_language, len(text), start)
        return TranslationResult(response["TranslatedText"], detected, response.get("TargetLanguageCode") or target_language)

    def _handle_client_error(
        self, exc: ClientError, text: str, source: str, target: str, start: float
    ) -> TranslationResult:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        exception_name = type(exc).__name__
        # Solo el código y el nombre de la excepción: el mensaje de AWS puede
        # incluir ARNs o fragmentos de la solicitud.
        self._log("aws_error", source, target, len(text), start, exception_name, code)

        # Con "auto", si el idioma detectado es el destino y AWS rechaza el par,
        # se devuelve el texto original con el idioma detectado.
        reported_source = exc.response.get("SourceLanguageCode")
        if code in ("UnsupportedLanguagePairException", "InvalidRequestException") and source == AUTO:
            if reported_source == target:
                return TranslationResult(text, target, target)

        if code in _THROTTLING:
            error = ApiError(429, "RATE_LIMITED")
        elif code in _BAD_REQUEST:
            reason, message = _BAD_REQUEST[code]
            error = ApiError(400, "VALIDATION_ERROR", message, details={"reason": reason})
        else:
            # AccessDenied, credenciales vencidas, ServiceUnavailable, InternalServer, etc.
            error = ServiceUnavailableError()
        raise _with_aws_cause(error, code, exception_name) from None

    @staticmethod
    def _log(
        event: str,
        source: str,
        target: str,
        chars: int,
        start: float,
        error_type: str | None = None,
        aws_error_code: str | None = None,
    ) -> None:
        extra: dict[str, Any] = {
            "event": f"translate.{event}",
            "sourceLanguage": source,
            "targetLanguage": target,
            "chars": chars,
            "durationMs": round((time.perf_counter() - start) * 1000, 1) if start else 0.0,
        }
        if error_type:
            extra["errorType"] = error_type
        if aws_error_code:
            extra["awsErrorCode"] = aws_error_code
        level = logging.WARNING if error_type else logging.INFO
        logger.log(level, "translate", extra=extra)


def _with_aws_cause(error: ApiError, aws_error_code: str | None, exception_name: str) -> ApiError:
    """Adjunta el origen AWS al error para diagnóstico local (scripts/translate_smoke.py).

    No se serializa: el handler común solo usa code, message y details.
    """
    error.aws_error_code = aws_error_code  # type: ignore[attr-defined]
    error.aws_exception = exception_name  # type: ignore[attr-defined]
    return error
