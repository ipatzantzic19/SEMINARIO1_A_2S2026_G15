"""Acceso a ``messages`` y difusión con ``pg_notify`` (PRO-16).

El SQL y su justificación están en docs/api/python-chat.md §6.

- Sin respaldo en memoria: si RDS falla, la excepción llega al servicio, que
  responde 503 (REST) o ``INTERNAL_ERROR`` (WebSocket). El único repositorio en
  memoria vive en las pruebas.
- ``insert_message`` hace INSERT y ``pg_notify`` en la MISMA transacción: el
  NOTIFY se entrega solo si el COMMIT tiene éxito y nunca hay un mensaje
  guardado sin su notificación (Node los hace por separado y descarta el
  error del NOTIFY).
- La amistad se comprueba dentro del propio INSERT (``WHERE EXISTS``): si
  dejaron de ser amigos entre la conexión y el envío, no se inserta nada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.common.errors import ServiceUnavailableError

CHANNEL = "chat_messages"
# pg_notify admite menos de 8000 bytes; se deja margen.
MAX_NOTIFY_BYTES = 7900

_ISO_MS = "YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\""


@dataclass(frozen=True)
class StoredMessage:
    """Mensaje persistido; ``created_at`` es ISO UTC con milisegundos y ``Z``."""

    id: str
    sender_id: str
    recipient_id: str
    body: str
    created_at: str
    read_at: str | None = None


@dataclass(frozen=True)
class HistoryCursor:
    """Posición para paginar hacia atrás: ``created_at`` (ISO) y, opcionalmente, ``id``."""

    created_at: str
    message_id: str | None = None


class NotFriends(Exception):
    """No existe amistad entre ambos (403 / ``FORBIDDEN``)."""


class PayloadTooLarge(Exception):
    """El payload de NOTIFY excedería el límite de PostgreSQL."""


class ChatRepository(Protocol):
    def friend_exists(self, user_id: str) -> bool: ...

    def are_friends(self, user_a: str, user_b: str) -> bool: ...

    def insert_message(
        self, sender_id: str, recipient_id: str, body: str, client_message_id: str | None
    ) -> StoredMessage:
        """Inserta y notifica en una transacción. Raises: NotFriends, PayloadTooLarge."""

    def list_messages(
        self, user_id: str, friend_id: str, after: HistoryCursor | None, limit: int
    ) -> list[StoredMessage]:
        """Más recientes primero; el servicio pide ``limite + 1`` para saber si hay más."""


def notify_payload(message: StoredMessage, client_message_id: str | None) -> str:
    """Mismo JSON que Node: ``clientMessageId`` solo si existe; UTF-8 sin escapar."""
    data: dict[str, Any] = {"messageId": message.id}
    if client_message_id is not None:
        data["clientMessageId"] = client_message_id
    data.update(
        senderId=message.sender_id,
        recipientId=message.recipient_id,
        body=message.body,
        createdAt=message.created_at,
    )
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


_FRIEND_EXISTS = "SELECT 1 FROM users WHERE id = %s::uuid"

_ARE_FRIENDS = (
    "SELECT 1 FROM friendships"
    " WHERE user_low_id = LEAST(%(a)s::uuid, %(b)s::uuid) AND user_high_id = GREATEST(%(a)s::uuid, %(b)s::uuid)"
)

# created_at lo fija RDS (una sola fuente de reloj para ambas instancias), truncado
# a milisegundos como el ISO de Node para que el cursor ``created_at < ts`` coincida.
_INSERT_MESSAGE = (
    "INSERT INTO messages (sender_id, recipient_id, content, created_at)"
    " SELECT %(sender)s::uuid, %(recipient)s::uuid, %(body)s, date_trunc('milliseconds', clock_timestamp())"
    " WHERE EXISTS (SELECT 1 FROM friendships"
    " WHERE user_low_id = LEAST(%(sender)s::uuid, %(recipient)s::uuid)"
    " AND user_high_id = GREATEST(%(sender)s::uuid, %(recipient)s::uuid))"
    " RETURNING id::text, sender_id::text, recipient_id::text, content,"
    f" to_char(created_at AT TIME ZONE 'UTC', '{_ISO_MS}')"
)

_NOTIFY = "SELECT pg_notify(%s, %s)"

# Mismo predicado de conversación que database/queries/conversation.sql (usa el
# índice messages_conversation_created_id_idx). Con cursor sin id (el de Node)
# se compara solo ``created_at``; con id, el par (created_at, id).
_LIST_MESSAGES = (
    "SELECT m.id::text, m.sender_id::text, m.recipient_id::text, m.content,"
    f" to_char(m.created_at AT TIME ZONE 'UTC', '{_ISO_MS}'),"
    f" to_char(m.read_at AT TIME ZONE 'UTC', '{_ISO_MS}')"
    " FROM messages m"
    " WHERE LEAST(m.sender_id, m.recipient_id) = LEAST(%(me)s::uuid, %(friend)s::uuid)"
    " AND GREATEST(m.sender_id, m.recipient_id) = GREATEST(%(me)s::uuid, %(friend)s::uuid)"
    " AND (%(ts)s::timestamptz IS NULL"
    " OR (%(cid)s::uuid IS NULL AND m.created_at < %(ts)s::timestamptz)"
    " OR (%(cid)s::uuid IS NOT NULL AND (m.created_at, m.id) < (%(ts)s::timestamptz, %(cid)s::uuid)))"
    " ORDER BY m.created_at DESC, m.id DESC"
    " LIMIT %(limit)s"
)


def _stored(row: Any) -> StoredMessage:
    # El RETURNING del INSERT trae 5 columnas (read_at es NULL al crear); el SELECT trae 6.
    read_at = row[5] if len(row) > 5 else None
    return StoredMessage(
        id=row[0], sender_id=row[1], recipient_id=row[2], body=row[3], created_at=row[4], read_at=read_at
    )


class PostgresChatRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def friend_exists(self, user_id: str) -> bool:
        with self._db.connection() as conn:
            return conn.execute(_FRIEND_EXISTS, (user_id,)).fetchone() is not None

    def are_friends(self, user_a: str, user_b: str) -> bool:
        if user_a == user_b:
            return False
        with self._db.connection() as conn:
            return conn.execute(_ARE_FRIENDS, {"a": user_a, "b": user_b}).fetchone() is not None

    def insert_message(
        self, sender_id: str, recipient_id: str, body: str, client_message_id: str | None
    ) -> StoredMessage:
        with self._db.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    _INSERT_MESSAGE, {"sender": sender_id, "recipient": recipient_id, "body": body}
                ).fetchone()
                if row is None:
                    raise NotFriends()
                message = _stored(row)
                payload = notify_payload(message, client_message_id)
                if len(payload.encode("utf-8")) > MAX_NOTIFY_BYTES:
                    # Dentro de la transacción: el ROLLBACK descarta el INSERT.
                    raise PayloadTooLarge()
                conn.execute(_NOTIFY, (CHANNEL, payload))
        return message

    def list_messages(
        self, user_id: str, friend_id: str, after: HistoryCursor | None, limit: int
    ) -> list[StoredMessage]:
        params = {
            "me": user_id,
            "friend": friend_id,
            "ts": after.created_at if after else None,
            "cid": after.message_id if after else None,
            "limit": limit,
        }
        with self._db.connection() as conn:
            rows = conn.execute(_LIST_MESSAGES, params).fetchall()
        return [_stored(row) for row in rows]


class UnavailableChatRepository:
    """Sin RDS configurado: toda consulta responde 503 (nunca memoria)."""

    def friend_exists(self, user_id: str) -> bool:
        raise ServiceUnavailableError()

    def are_friends(self, user_a: str, user_b: str) -> bool:
        raise ServiceUnavailableError()

    def insert_message(
        self, sender_id: str, recipient_id: str, body: str, client_message_id: str | None
    ) -> StoredMessage:
        raise ServiceUnavailableError()

    def list_messages(
        self, user_id: str, friend_id: str, after: HistoryCursor | None, limit: int
    ) -> list[StoredMessage]:
        raise ServiceUnavailableError()
