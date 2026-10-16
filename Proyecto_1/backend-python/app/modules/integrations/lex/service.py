"""Bot de la Facultad con Amazon Lex V2 (RecognizeText).

- El estado de la conversación vive en Lex, no en la EC2: Node y Python usan el
  mismo bot, alias, locale y la misma derivación de ``sessionId``, así el ALB
  puede alternar backends sin cortar la conversación.
- El ``sessionId`` del cliente nunca llega a Lex tal cual: se deriva con el
  ``sub`` del usuario (ver ``lex_session_id``), lo que liga la sesión al usuario
  y cumple el patrón de Lex.
- Solo se devuelven mensajes ``PlainText``.
- Los logs registran intent, estado y cantidad de mensajes; nunca el texto del
  usuario, las respuestas ni el sessionId.

Referencias y decisiones: docs/api/bot.md.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.common.errors import ApiError, ServiceUnavailableError
from app.config import LexSettings

logger = logging.getLogger("semisocial.lex")

# Respuesta cuando Lex no devuelve ningún mensaje de texto (decisión PRO-19).
EMPTY_RESPONSE_MESSAGE = "No tengo una respuesta para eso en este momento. Intenta reformular tu consulta."

# Throttling y dos mensajes simultáneos en la misma sesión: "intente de nuevo".
_RETRYABLE = {"ThrottlingException", "ConflictException"}


def lex_session_id(cognito_sub: str, client_session_id: str) -> str:
    """``"u" + hex(SHA-256(sub + ":" + sessionId))[:64]`` (65 caracteres, ``[0-9a-z]``).

    Node debe producir exactamente el mismo valor (vector de prueba en bot.md).
    """
    digest = hashlib.sha256(f"{cognito_sub}:{client_session_id}".encode("utf-8")).hexdigest()
    return "u" + digest[:64]


class BotService:
    """Envuelve el cliente ``lexv2-runtime``; el cliente se crea en la primera llamada."""

    def __init__(self, settings: LexSettings, client_factory: Callable[[], Any]) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: Any = None
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return self._settings.configured

    def _get_client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._client_factory()
        return self._client

    def send(self, cognito_sub: str, client_session_id: str, text: str) -> list[str]:
        if not self.configured:
            self._log("not_configured", None, 0.0, len(text), error_type="LexNotConfigured")
            raise ServiceUnavailableError()

        start = time.perf_counter()
        try:
            response = self._get_client().recognize_text(
                botId=self._settings.bot_id,
                botAliasId=self._settings.bot_alias_id,
                localeId=self._settings.locale_id,
                sessionId=lex_session_id(cognito_sub, client_session_id),
                text=text,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            self._log("aws_error", None, start, len(text), error_type=type(exc).__name__, aws_error_code=code)
            error = ApiError(429, "RATE_LIMITED") if code in _RETRYABLE else ServiceUnavailableError()
            raise _with_aws_cause(error, code, type(exc).__name__) from None
        except BotoCoreError as exc:
            # Sin credenciales, sin red (timeout, DNS, endpoint) o región inválida.
            self._log("aws_unavailable", None, start, len(text), error_type=type(exc).__name__)
            raise _with_aws_cause(ServiceUnavailableError(), None, type(exc).__name__) from None

        messages = [
            message["content"]
            for message in response.get("messages") or []
            if message.get("contentType", "PlainText") == "PlainText" and (message.get("content") or "").strip()
        ]
        intent = (response.get("sessionState") or {}).get("intent") or {}
        if not messages:
            self._log("empty_response", intent, start, len(text), level=logging.WARNING)
            return [EMPTY_RESPONSE_MESSAGE]
        self._log("replied", intent, start, len(text), message_count=len(messages))
        return messages

    @staticmethod
    def _log(
        event: str,
        intent: dict[str, Any] | None,
        start: float,
        chars: int,
        *,
        error_type: str | None = None,
        aws_error_code: str | None = None,
        message_count: int | None = None,
        level: int | None = None,
    ) -> None:
        extra: dict[str, Any] = {
            "event": f"lex.{event}",
            "chars": chars,
            "durationMs": round((time.perf_counter() - start) * 1000, 1) if start else 0.0,
        }
        if intent:
            extra["intentName"] = intent.get("name")
            extra["intentState"] = intent.get("state")
        if message_count is not None:
            extra["messageCount"] = message_count
        if error_type:
            extra["errorType"] = error_type
        if aws_error_code:
            extra["awsErrorCode"] = aws_error_code
        if level is None:
            level = logging.WARNING if error_type else logging.INFO
        logger.log(level, "lex", extra=extra)


def _with_aws_cause(error: ApiError, aws_error_code: str | None, exception_name: str) -> ApiError:
    """Adjunta el origen AWS al error para diagnóstico local (scripts/lex_smoke.py).

    No se serializa: el handler común solo usa code, message y details.
    """
    error.aws_error_code = aws_error_code  # type: ignore[attr-defined]
    error.aws_exception = exception_name  # type: ignore[attr-defined]
    return error
