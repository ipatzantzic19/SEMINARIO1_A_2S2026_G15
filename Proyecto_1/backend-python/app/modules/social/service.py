"""Usuarios y solicitudes de amistad (PRO-15).

Reglas y códigos: docs/api/python-friends.md §3. Resumen:

- Todas las rutas exigen perfil completo (``require_complete_profile`` en el router).
- La identidad sale del ``sub`` del token (``users.id`` vía ``get_by_sub``); el
  cliente nunca elige quién es el solicitante ni quién responde.
- Un destinatario inexistente o con perfil incompleto responde igual (404): los
  perfiles incompletos no son visibles (contract.md).
- Logs sin PII: solo evento y motivo, nunca ids, nombres ni correos.
"""

from __future__ import annotations

import logging
from datetime import timezone
from collections.abc import Callable
from typing import Any, Literal, TypeVar
from uuid import UUID

from app.common.auth import Principal
from app.common.errors import ApiError, ForbiddenError, ServiceUnavailableError
from app.modules.social.cursor import InvalidCursor, decode_cursor, encode_cursor
from app.modules.social.repository import (
    AddresseeNotFound,
    AlreadyAnswered,
    AlreadyFriends,
    FriendsRepository,
    NotAddressee,
    PublicUserRecord,
    RequestNotFound,
    RequestPending,
    RequestRecord,
)
from app.modules.users.directory import UserDirectory, log_event


T = TypeVar("T")

_DOMAIN_ERRORS = (AddresseeNotFound, AlreadyAnswered, AlreadyFriends, NotAddressee, RequestNotFound, RequestPending)


def _error(status: int, code: str, message: str, reason: str | None = None) -> ApiError:
    return ApiError(status, code, message, details={"reason": reason} if reason else None)


class SocialService:
    def __init__(self, directory: UserDirectory, friends: FriendsRepository) -> None:
        self._directory = directory
        self._users = directory.users
        self._friends = friends

    def _call(self, operation: Callable[[], T]) -> T:
        """Deja pasar errores de negocio; cualquier otra falla de RDS es 503 (sin memoria)."""
        try:
            return operation()
        except (ApiError, *_DOMAIN_ERRORS):
            raise
        except Exception as exc:  # noqa: BLE001
            # psycopg/pool: el mensaje puede contener datos de conexión; solo el tipo.
            log_event("friends.db_error", logging.ERROR, errorType=type(exc).__name__)
            raise ServiceUnavailableError() from None

    # -- Formato de respuesta ---------------------------------------------

    def _public_user(self, user: PublicUserRecord) -> dict[str, Any]:
        return {
            "userId": user.id,
            "fullName": user.full_name,
            "profileImageUrl": self._directory.image_url(user.profile_image_key),
        }

    def _friend_request(self, record: RequestRecord) -> dict[str, Any]:
        # Igual que Date.toISOString() de Node: milisegundos truncados y "Z".
        moment = record.created_at.astimezone(timezone.utc)
        created_at = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
        return {
            "requestId": record.id,
            "requester": self._public_user(record.requester),
            "addressee": self._public_user(record.addressee),
            "status": record.status,
            "createdAt": created_at,
        }

    def _me(self, principal: Principal) -> str:
        record = self._directory.call(lambda: self._users.get_by_sub(principal.sub))
        if record is None or not record.profile_complete:
            # No ocurre tras require_complete_profile salvo una carrera con RDS.
            raise ForbiddenError(
                "Complete su perfil para usar esta funcionalidad.", details={"reason": "PROFILE_INCOMPLETE"}
            )
        return record.id

    # -- GET /users ---------------------------------------------------------

    def list_non_friends(self, principal: Principal, cursor: str | None, limit: int) -> dict[str, Any]:
        after = None
        if cursor is not None:
            try:
                after = decode_cursor(cursor)
            except InvalidCursor:
                raise _error(400, "VALIDATION_ERROR", "El cursor no es válido.", "INVALID_CURSOR") from None
        me_id = self._me(principal)
        rows = self._call(lambda: self._friends.list_non_friends(me_id, after, limit + 1))
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1]
            next_cursor = encode_cursor(last.cursor_at, last.user.id)
        return {"items": [self._public_user(row.user) for row in page], "nextCursor": next_cursor}

    # -- GET /friend-requests -------------------------------------------------

    def list_requests(self, principal: Principal) -> list[dict[str, Any]]:
        me_id = self._me(principal)
        records = self._call(lambda: self._friends.list_requests(me_id))
        return [self._friend_request(record) for record in records]

    # -- POST /friend-requests ------------------------------------------------

    def create_request(self, principal: Principal, addressee_id: UUID) -> dict[str, Any]:
        me_id = self._me(principal)
        target = str(addressee_id)
        if target == me_id:
            raise _error(
                400, "VALIDATION_ERROR", "No puedes enviarte una solicitud de amistad a ti mismo.", "SELF_REQUEST"
            )
        try:
            record = self._call(lambda: self._friends.create_request(me_id, target))
        except AddresseeNotFound:
            raise _error(404, "NOT_FOUND", "El usuario destinatario no existe.") from None
        except AlreadyFriends:
            raise _error(
                409, "CONFLICT", "Ya existe una relación de amistad entre ambos usuarios.", "ALREADY_FRIENDS"
            ) from None
        except RequestPending:
            raise _error(
                409, "CONFLICT", "Ya existe una solicitud de amistad pendiente con este usuario.", "REQUEST_PENDING"
            ) from None
        log_event("friends.request_created")
        return self._friend_request(record)

    # -- PATCH /friend-requests/{requestId} -----------------------------------

    def answer_request(
        self, principal: Principal, request_id: UUID, decision: Literal["accepted", "rejected"]
    ) -> dict[str, Any]:
        me_id = self._me(principal)
        try:
            record = self._call(lambda: self._friends.answer_request(str(request_id), me_id, decision))
        except RequestNotFound:
            raise _error(404, "NOT_FOUND", "Solicitud de amistad no encontrada.") from None
        except NotAddressee:
            raise _error(
                403,
                "FORBIDDEN",
                "Solo el destinatario puede responder a esta solicitud de amistad.",
                "NOT_ADDRESSEE",
            ) from None
        except AlreadyAnswered:
            raise _error(
                400, "VALIDATION_ERROR", "La solicitud de amistad ya fue respondida previamente.", "ALREADY_ANSWERED"
            ) from None
        except AlreadyFriends:
            # La amistad existía sin pasar por esta solicitud: se revirtió todo.
            log_event("friends.accept_conflict", logging.ERROR, reason="FRIENDSHIP_EXISTS")
            raise _error(
                409, "CONFLICT", "Ya existe una relación de amistad entre ambos usuarios.", "ALREADY_FRIENDS"
            ) from None
        log_event("friends.request_answered", reason=decision)
        return self._friend_request(record)

    # -- GET /friends -----------------------------------------------------------

    def list_friends(self, principal: Principal) -> list[dict[str, Any]]:
        me_id = self._me(principal)
        friends = self._call(lambda: self._friends.list_friends(me_id))
        return [self._public_user(friend) for friend in friends]
