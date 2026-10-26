"""Reglas del chat (PRO-16). Protocolo y decisiones: docs/api/python-chat.md.

- Autorización del handshake con el mismo orden y los mismos códigos de cierre
  que Node (chat.gateway.ts): 4401 → 4400 → 4401 → 4403.
- La identidad del emisor sale SIEMPRE del token; el cliente nunca la fija.
- Logs sin PII: solo evento y tipo de error; nunca token, ids ni contenido.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import UUID

from app.common.auth import CognitoTokenVerifier, KeySourceUnavailable, TokenInvalid
from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.chat.repository import (
    ChatRepository,
    HistoryCursor,
    NotFriends,
    PayloadTooLarge,
    StoredMessage,
)
from app.modules.social.cursor import InvalidCursor, decode_cursor
from app.modules.users.directory import log_event
from app.modules.users.repository import UsersRepository

T = TypeVar("T")

MAX_BODY_CHARS = 4000
DEFAULT_HISTORY_LIMIT = 50  # Node: 50 por defecto (el OpenAPI común declara 20).
MAX_CLIENT_MESSAGE_ID = 64

_BAD_CHARS_RE = re.compile(r"[\x00\ud800-\udfff]")  # PostgreSQL rechaza NUL; surrogates sueltos no son UTF-8.
_BARE_TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z$")


class HandshakeRejected(Exception):
    """Se cierra el WebSocket (tras aceptar el upgrade, como Node) con este código."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class ChatError(Exception):
    """Error de un frame ``message:send``: se responde con el evento ``error``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.client_message_id: str | None = None


@dataclass(frozen=True)
class ChatIdentity:
    user_id: str
    friend_id: str


def validate_body(body: object) -> str:
    """Recorta y valida el texto: 1..4000 caracteres (``char_length`` de la BD)."""
    if not isinstance(body, str):
        raise ChatError("VALIDATION_ERROR", "El mensaje debe contener entre 1 y 4000 caracteres.")
    trimmed = body.strip()
    if not trimmed or len(trimmed) > MAX_BODY_CHARS or _BAD_CHARS_RE.search(trimmed):
        raise ChatError("VALIDATION_ERROR", "El mensaje debe contener entre 1 y 4000 caracteres.")
    return trimmed


def parse_history_cursor(cursor: str) -> HistoryCursor:
    """Acepta el cursor de Node (ISO UTC desnudo) y el común (``ts#uuid`` en base64url)."""
    if _BARE_TIMESTAMP_RE.match(cursor):
        return HistoryCursor(created_at=cursor)
    position = decode_cursor(cursor)
    return HistoryCursor(created_at=position.created_at, message_id=position.user_id)


class ChatService:
    def __init__(self, verifier: CognitoTokenVerifier, users: UsersRepository, repository: ChatRepository) -> None:
        self._verifier = verifier
        self._users = users
        self._repository = repository

    def _db(self, operation: Callable[[], T], event: str) -> T:
        try:
            return operation()
        except (ApiError, NotFriends, PayloadTooLarge):
            raise
        except Exception as exc:  # noqa: BLE001
            # psycopg/pool: el mensaje puede contener datos de conexión; solo el tipo.
            log_event(event, logging.ERROR, errorType=type(exc).__name__)
            raise ServiceUnavailableError() from None

    # -- WebSocket: handshake (bloqueante; se ejecuta en el threadpool) ----------

    def authorize(self, token: str | None, friend_id: str | None) -> ChatIdentity:
        if not token:
            raise HandshakeRejected(4401, "Unauthorized: token is required")
        if not friend_id:
            raise HandshakeRejected(4400, "Bad Request: friendId is required")
        try:
            principal = self._verifier.verify(token)
        except TokenInvalid:
            raise HandshakeRejected(4401, "Unauthorized: invalid token") from None
        except KeySourceUnavailable:
            log_event("chat.jwks_unavailable", logging.ERROR)
            raise HandshakeRejected(1011, "Internal Error") from None

        try:
            user = self._users.get_by_sub(principal.sub)
        except Exception as exc:  # noqa: BLE001
            log_event("chat.db_error", logging.ERROR, errorType=type(exc).__name__)
            raise HandshakeRejected(1011, "Internal Error") from None
        if user is None:
            raise HandshakeRejected(4401, "Unauthorized: invalid token")
        if not user.profile_complete:
            raise HandshakeRejected(4403, "Forbidden: PROFILE_INCOMPLETE")

        # Node: un friendId que no es UUID termina en "no son amigos" (4403).
        try:
            friend = str(UUID(friend_id))
        except ValueError:
            raise HandshakeRejected(4403, "Forbidden: NOT_FRIENDS") from None
        try:
            friends = self._repository.are_friends(user.id, friend)
        except Exception as exc:  # noqa: BLE001
            log_event("chat.db_error", logging.ERROR, errorType=type(exc).__name__)
            raise HandshakeRejected(1011, "Internal Error") from None
        if not friends:
            raise HandshakeRejected(4403, "Forbidden: NOT_FRIENDS")
        return ChatIdentity(user_id=user.id, friend_id=friend)

    # -- WebSocket: envío (bloqueante) -----------------------------------------

    def send(self, identity: ChatIdentity, data: Any) -> None:
        """Valida y persiste. El ack NO se devuelve aquí: llega por LISTEN/NOTIFY."""
        data = data if isinstance(data, dict) else {}
        client_id = data.get("clientMessageId")
        if not isinstance(client_id, str) or len(client_id) > MAX_CLIENT_MESSAGE_ID:
            client_id = None
        try:
            if data.get("recipientId") != identity.friend_id:
                raise ChatError("VALIDATION_ERROR", "El recipientId debe coincidir con la conversación activa.")
            body = validate_body(data.get("body"))
            try:
                self._db(
                    lambda: self._repository.insert_message(identity.user_id, identity.friend_id, body, client_id),
                    "chat.db_error",
                )
            except NotFriends:
                raise ChatError("FORBIDDEN", "Solo amigos confirmados pueden enviarse mensajes.") from None
            except PayloadTooLarge:
                raise ChatError(
                    "VALIDATION_ERROR", "El mensaje es demasiado largo para difundirse; acórtelo."
                ) from None
            except ServiceUnavailableError:
                raise ChatError("INTERNAL_ERROR", "Error al persistir el mensaje.") from None
        except ChatError as exc:
            exc.client_message_id = client_id
            raise
        log_event("chat.message_sent")

    # -- REST: historial -----------------------------------------------------------

    def history(self, sub: str, friend_id: UUID, cursor: str | None, limit: int) -> dict[str, Any]:
        after = None
        if cursor is not None:
            try:
                after = parse_history_cursor(cursor)
            except InvalidCursor:
                raise ApiError(
                    400, "VALIDATION_ERROR", "El cursor no es válido.", details={"reason": "INVALID_CURSOR"}
                ) from None
        me = self._db(lambda: self._users.get_by_sub(sub), "chat.db_error")
        if me is None or not me.profile_complete:
            raise ApiError(
                403, "FORBIDDEN", "Complete su perfil para usar esta funcionalidad.",
                details={"reason": "PROFILE_INCOMPLETE"},
            )
        friend = str(friend_id)
        if not self._db(lambda: self._repository.friend_exists(friend), "chat.db_error"):
            raise ApiError(404, "NOT_FOUND", "El usuario destinatario no existe.")
        if not self._db(lambda: self._repository.are_friends(me.id, friend), "chat.db_error"):
            raise ApiError(
                403,
                "FORBIDDEN",
                "Solo amigos confirmados pueden consultar el historial de chat.",
                details={"reason": "NOT_FRIENDS"},
            )
        rows = self._db(lambda: self._repository.list_messages(me.id, friend, after, limit + 1), "chat.db_error")
        page = rows[:limit]
        next_cursor = page[-1].created_at if len(rows) > limit and page else None
        # Node responde en orden cronológico ascendente.
        return {"items": [_message_json(m) for m in reversed(page)], "nextCursor": next_cursor}


def _message_json(message: StoredMessage) -> dict[str, Any]:
    return {
        "messageId": message.id,
        "senderId": message.sender_id,
        "recipientId": message.recipient_id,
        "body": message.body,
        "createdAt": message.created_at,
        "readAt": message.read_at,
    }
