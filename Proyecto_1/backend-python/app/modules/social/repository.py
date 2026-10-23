"""Acceso a ``friend_requests`` y ``friendships`` (PRO-15).

El SQL completo y su justificación están en docs/api/python-friends.md §5.

- Sin respaldo en memoria: si RDS falla, la excepción llega al servicio, que
  responde 503. El único repositorio en memoria vive en las pruebas.
- Las reglas de negocio se señalan con excepciones de dominio; las restricciones
  UNIQUE/FK de la BD se traducen aquí (``friend_requests_one_pending_pair_idx``,
  claves de ``friendships``).
- No se usa bloqueo consultivo: ``PATCH`` serializa con ``FOR UPDATE`` y
  ``UPDATE ... AND status = 'pending'``. Queda una ventana residual documentada
  en python-friends.md §8 (creación de solicitud concurrente con una aceptación).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

import psycopg

from app.common.errors import ServiceUnavailableError
from app.modules.social.cursor import CursorPosition

PENDING_PAIR_INDEX = "friend_requests_one_pending_pair_idx"


@dataclass(frozen=True)
class PublicUserRecord:
    id: str
    full_name: str
    profile_image_key: str | None


@dataclass(frozen=True)
class PersonRow:
    """Fila de ``GET /users``; ``cursor_at`` es el texto de ``to_char`` (6 decimales)."""

    user: PublicUserRecord
    cursor_at: str


@dataclass(frozen=True)
class RequestRecord:
    id: str
    status: str
    created_at: datetime
    requester: PublicUserRecord
    addressee: PublicUserRecord


class AddresseeNotFound(Exception):
    """El destinatario no existe o su perfil está incompleto (404, mismo mensaje)."""


class AlreadyFriends(Exception):
    """Ya existe la amistad (409 ALREADY_FRIENDS)."""


class RequestPending(Exception):
    """Ya hay una solicitud pendiente entre ambos, en cualquier dirección (409)."""


class RequestNotFound(Exception):
    """La solicitud no existe (404)."""


class NotAddressee(Exception):
    """Quien responde no es el destinatario (403 NOT_ADDRESSEE)."""


class AlreadyAnswered(Exception):
    """La solicitud ya no está pendiente (400 ALREADY_ANSWERED)."""


class FriendsRepository(Protocol):
    def list_non_friends(self, me_id: str, after: CursorPosition | None, limit: int) -> list[PersonRow]:
        """Hasta ``limit`` filas (el servicio pide ``limite + 1`` para saber si hay más)."""

    def list_requests(self, me_id: str) -> list[RequestRecord]:
        """Solicitudes ``pending`` enviadas y recibidas, más recientes primero."""

    def list_friends(self, me_id: str) -> list[PublicUserRecord]: ...

    def create_request(self, requester_id: str, addressee_id: str) -> RequestRecord:
        """Raises: AddresseeNotFound, AlreadyFriends, RequestPending."""

    def answer_request(
        self, request_id: str, responder_id: str, decision: Literal["accepted", "rejected"]
    ) -> RequestRecord:
        """Raises: RequestNotFound, NotAddressee, AlreadyAnswered, AlreadyFriends."""


_PERSON = "u.id::text, u.full_name, u.profile_image_key"

_LIST_NON_FRIENDS = (
    f"SELECT {_PERSON},"
    " to_char(u.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS cursor_at"
    " FROM users u"
    " WHERE u.id <> %(me)s::uuid"
    " AND u.profile_image_key IS NOT NULL"
    " AND NOT EXISTS (SELECT 1 FROM friendships f"
    " WHERE f.user_low_id = LEAST(u.id, %(me)s::uuid)"
    " AND f.user_high_id = GREATEST(u.id, %(me)s::uuid))"
    " AND (%(ts)s::timestamptz IS NULL OR (u.created_at, u.id) < (%(ts)s::timestamptz, %(cid)s::uuid))"
    " ORDER BY u.created_at DESC, u.id DESC"
    " LIMIT %(limit)s"
)

_REQUEST_COLUMNS = (
    "fr.id::text, fr.status::text, fr.created_at,"
    " rq.id::text, rq.full_name, rq.profile_image_key,"
    " ad.id::text, ad.full_name, ad.profile_image_key"
)
_REQUEST_JOINS = (
    " FROM friend_requests fr"
    " JOIN users rq ON rq.id = fr.requester_id"
    " JOIN users ad ON ad.id = fr.addressee_id"
)

_LIST_REQUESTS = (
    f"SELECT {_REQUEST_COLUMNS}{_REQUEST_JOINS}"
    " WHERE fr.status = 'pending'"
    " AND (fr.requester_id = %(me)s::uuid OR fr.addressee_id = %(me)s::uuid)"
    " ORDER BY fr.created_at DESC, fr.id DESC"
)

_LIST_FRIENDS = (
    f"SELECT {_PERSON}"
    " FROM (SELECT user_high_id AS friend_id FROM friendships WHERE user_low_id = %(me)s::uuid"
    " UNION ALL"
    " SELECT user_low_id AS friend_id FROM friendships WHERE user_high_id = %(me)s::uuid) f"
    " JOIN users u ON u.id = f.friend_id"
    " ORDER BY u.full_name ASC, u.id ASC"
)

_PEOPLE_BY_ID = "SELECT id::text, full_name, profile_image_key FROM users WHERE id IN (%s::uuid, %s::uuid)"

_ARE_FRIENDS = (
    "SELECT 1 FROM friendships"
    " WHERE user_low_id = LEAST(%(a)s::uuid, %(b)s::uuid) AND user_high_id = GREATEST(%(a)s::uuid, %(b)s::uuid)"
)

_INSERT_REQUEST = (
    "INSERT INTO friend_requests (requester_id, addressee_id) VALUES (%s::uuid, %s::uuid)"
    " RETURNING id::text, status::text, created_at"
)

_LOCK_REQUEST = (
    f"SELECT {_REQUEST_COLUMNS}{_REQUEST_JOINS}"
    " WHERE fr.id = %s::uuid FOR UPDATE OF fr"
)

_ANSWER_REQUEST = (
    "UPDATE friend_requests SET status = %(status)s::friend_request_status, responded_at = now()"
    " WHERE id = %(id)s::uuid AND status = 'pending' RETURNING status::text"
)

_INSERT_FRIENDSHIP = (
    "INSERT INTO friendships (user_low_id, user_high_id, request_id)"
    " VALUES (LEAST(%(a)s::uuid, %(b)s::uuid), GREATEST(%(a)s::uuid, %(b)s::uuid), %(request)s::uuid)"
)


def _user(row: Any, offset: int = 0) -> PublicUserRecord:
    return PublicUserRecord(id=row[offset], full_name=row[offset + 1], profile_image_key=row[offset + 2])


def _request(row: Any) -> RequestRecord:
    return RequestRecord(id=row[0], status=row[1], created_at=row[2], requester=_user(row, 3), addressee=_user(row, 6))


def _constraint(exc: psycopg.Error) -> str:
    return getattr(getattr(exc, "diag", None), "constraint_name", None) or ""


class PostgresFriendsRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def list_non_friends(self, me_id: str, after: CursorPosition | None, limit: int) -> list[PersonRow]:
        params = {
            "me": me_id,
            "ts": after.created_at if after else None,
            "cid": after.user_id if after else None,
            "limit": limit,
        }
        with self._db.connection() as conn:
            rows = conn.execute(_LIST_NON_FRIENDS, params).fetchall()
        return [PersonRow(user=_user(row), cursor_at=row[3]) for row in rows]

    def list_requests(self, me_id: str) -> list[RequestRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(_LIST_REQUESTS, {"me": me_id}).fetchall()
        return [_request(row) for row in rows]

    def list_friends(self, me_id: str) -> list[PublicUserRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(_LIST_FRIENDS, {"me": me_id}).fetchall()
        return [_user(row) for row in rows]

    def create_request(self, requester_id: str, addressee_id: str) -> RequestRecord:
        try:
            with self._db.connection() as conn:
                with conn.transaction():
                    people = {
                        row[0]: _user(row) for row in conn.execute(_PEOPLE_BY_ID, (requester_id, addressee_id)).fetchall()
                    }
                    addressee = people.get(addressee_id)
                    if addressee is None or addressee.profile_image_key is None:
                        raise AddresseeNotFound()
                    requester = people.get(requester_id)
                    if requester is None:
                        # El solicitante salió de la BD entre la autenticación y esta consulta.
                        raise RuntimeError("solicitante inexistente")
                    if conn.execute(_ARE_FRIENDS, {"a": requester_id, "b": addressee_id}).fetchone() is not None:
                        raise AlreadyFriends()
                    row = conn.execute(_INSERT_REQUEST, (requester_id, addressee_id)).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            if _constraint(exc) == PENDING_PAIR_INDEX:
                raise RequestPending() from None
            raise
        except psycopg.errors.ForeignKeyViolation:
            raise AddresseeNotFound() from None
        return RequestRecord(id=row[0], status=row[1], created_at=row[2], requester=requester, addressee=addressee)

    def answer_request(
        self, request_id: str, responder_id: str, decision: Literal["accepted", "rejected"]
    ) -> RequestRecord:
        try:
            with self._db.connection() as conn:
                with conn.transaction():
                    row = conn.execute(_LOCK_REQUEST, (request_id,)).fetchone()
                    if row is None:
                        raise RequestNotFound()
                    record = _request(row)
                    if record.addressee.id != responder_id:
                        raise NotAddressee()
                    if record.status != "pending":
                        raise AlreadyAnswered()
                    updated = conn.execute(_ANSWER_REQUEST, {"status": decision, "id": request_id}).fetchone()
                    if updated is None:
                        raise AlreadyAnswered()
                    if decision == "accepted":
                        conn.execute(
                            _INSERT_FRIENDSHIP,
                            {"a": record.requester.id, "b": record.addressee.id, "request": request_id},
                        )
        except psycopg.errors.UniqueViolation:
            # friendships_pkey o friendships_request_id_key: la amistad ya existía
            # fuera de este flujo. ROLLBACK completo; la solicitud sigue pendiente.
            raise AlreadyFriends() from None
        return RequestRecord(
            id=record.id,
            status=updated[0],
            created_at=record.created_at,
            requester=record.requester,
            addressee=record.addressee,
        )


class UnavailableFriendsRepository:
    """Sin RDS configurado: toda consulta responde 503 (nunca memoria)."""

    def list_non_friends(self, me_id: str, after: CursorPosition | None, limit: int) -> list[PersonRow]:
        raise ServiceUnavailableError()

    def list_requests(self, me_id: str) -> list[RequestRecord]:
        raise ServiceUnavailableError()

    def list_friends(self, me_id: str) -> list[PublicUserRecord]:
        raise ServiceUnavailableError()

    def create_request(self, requester_id: str, addressee_id: str) -> RequestRecord:
        raise ServiceUnavailableError()

    def answer_request(
        self, request_id: str, responder_id: str, decision: Literal["accepted", "rejected"]
    ) -> RequestRecord:
        raise ServiceUnavailableError()
