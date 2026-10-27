"""Cursor común de ``GET /users`` (docs/api/python-friends.md §4).

Formato: ``base64url_sin_relleno("<created_at UTC con 6 decimales>Z#<uuid>")``,
por ejemplo ``2026-10-20T12:00:00.123456Z#22222222-2222-4222-8222-222222222222``.

El texto del instante lo genera PostgreSQL con ``to_char`` (microsegundos
exactos): ni Python ni Node pasan por ``datetime``/``Date``, que perderían
precisión. Al leer se acepta también base64 estándar, con o sin ``=``.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

_TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$")
_MAX_CURSOR_LENGTH = 200


class InvalidCursor(ValueError):
    """El cursor no tiene el formato común (se responde 400 INVALID_CURSOR)."""


@dataclass(frozen=True)
class CursorPosition:
    created_at: str  # "YYYY-MM-DDTHH:MM:SS.ffffffZ"
    user_id: str  # UUID en minúsculas


def encode_cursor(created_at: str, user_id: str) -> str:
    raw = f"{created_at}#{user_id}".encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str) -> CursorPosition:
    if not cursor or len(cursor) > _MAX_CURSOR_LENGTH:
        raise InvalidCursor()
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        # Se normaliza el alfabeto estándar (+/) al de URL (-_) y se valida el resto.
        raw = base64.b64decode(padded.replace("+", "-").replace("/", "_"), altchars=b"-_", validate=True)
        text = raw.decode("utf-8")
    except (binascii.Error, ValueError):
        raise InvalidCursor() from None

    created_at, separator, user_id = text.partition("#")
    if not separator or not _TIMESTAMP_RE.match(created_at):
        raise InvalidCursor()
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        parsed = UUID(user_id)
    except ValueError:
        raise InvalidCursor() from None
    return CursorPosition(created_at=created_at, user_id=str(parsed))
