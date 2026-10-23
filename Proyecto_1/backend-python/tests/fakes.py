"""Dobles de prueba de RDS, Cognito y S3 (solo pruebas; la app nunca usa memoria)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Literal

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.cognito.gateway import AuthChallenge, AuthOutcome, AuthTokens, SignUpResult
from app.modules.integrations.s3.objects import ObjectInfo
from app.modules.social.cursor import CursorPosition
from app.modules.social.repository import (
    AddresseeNotFound,
    AlreadyAnswered,
    AlreadyFriends,
    NotAddressee,
    PersonRow,
    PublicUserRecord,
    RequestNotFound,
    RequestPending,
    RequestRecord,
)
from app.modules.users.repository import DuplicateUser, ProfileChanges, SyncCommitFailed, UserRecord

CLOCK_START = datetime(2026, 10, 20, 12, 0, 0, 123456, tzinfo=timezone.utc)


class InMemoryUsersRepository:
    """Implementa el Protocol de ``app/modules/users/repository.py`` en memoria,
    con las mismas reglas UNIQUE y de transacción que PostgreSQL."""

    def __init__(self) -> None:
        self.rows: dict[str, UserRecord] = {}
        self.fail_with: Exception | None = None  # simula RDS caído en cualquier llamada
        self.fail_commit = False  # simula COMMIT fallido tras before_commit
        self.created: dict[str, datetime] = {}  # users.created_at (microsegundos) por users.id

    def add(
        self, sub: str, *, email: str, full_name: str, dpi: str, complete: bool, user_id: str | None = None
    ) -> UserRecord:
        record = UserRecord(
            id=user_id or str(uuid.uuid4()),
            cognito_sub=sub,
            email=email,
            full_name=full_name,
            dpi=dpi,
            profile_image_key=f"Fotos_Perfil/public/{sub}/00000000-0000-4000-8000-000000000001.webp" if complete else None,
            face_reference_key=f"Fotos_Perfil/references/{sub}/00000000-0000-4000-8000-000000000001.webp"
            if complete
            else None,
        )
        self.rows[sub] = record
        self.created[record.id] = CLOCK_START + timedelta(seconds=len(self.created), microseconds=len(self.created))
        return record

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def profile_complete(self, cognito_sub: str) -> bool | None:
        self._check()
        row = self.rows.get(cognito_sub)
        return None if row is None else row.profile_complete

    def get_by_sub(self, cognito_sub: str) -> UserRecord | None:
        self._check()
        return self.rows.get(cognito_sub)

    def find_conflicts(
        self, *, email: str | None = None, dpi: str | None = None, exclude_sub: str | None = None
    ) -> list[str]:
        self._check()
        others = [r for r in self.rows.values() if r.cognito_sub != exclude_sub]
        found = []
        if email is not None and any(r.email.lower() == email.lower() for r in others):
            found.append("email")
        if dpi is not None and any(r.dpi == dpi for r in others):
            found.append("dpi")
        return found

    def insert(self, *, cognito_sub: str, email: str, full_name: str, dpi: str) -> UserRecord:
        self._check()
        if cognito_sub in self.rows:
            raise DuplicateUser("cognito_sub")
        conflicts = self.find_conflicts(email=email, dpi=dpi)
        if conflicts:
            raise DuplicateUser(conflicts[0])
        return self.add(cognito_sub, email=email, full_name=full_name, dpi=dpi, complete=False)

    def complete_profile(self, cognito_sub: str, profile_image_key: str, face_reference_key: str) -> UserRecord | None:
        self._check()
        row = self.rows.get(cognito_sub)
        if row is None or row.profile_image_key is not None:
            return None
        updated = replace(row, profile_image_key=profile_image_key, face_reference_key=face_reference_key)
        self.rows[cognito_sub] = updated
        return updated

    def update_profile(
        self, cognito_sub: str, changes: ProfileChanges, before_commit: Callable[[], None]
    ) -> UserRecord | None:
        self._check()
        row = self.rows.get(cognito_sub)
        if row is None:
            return None
        if changes.dpi is not None and self.find_conflicts(dpi=changes.dpi, exclude_sub=cognito_sub):
            raise DuplicateUser("dpi")
        updated = replace(
            row,
            full_name=changes.full_name or row.full_name,
            dpi=changes.dpi or row.dpi,
            profile_image_key=changes.profile_image_key or row.profile_image_key,
            face_reference_key=changes.face_reference_key or row.face_reference_key,
        )
        before_commit()  # si lanza, no se guarda nada (rollback)
        if self.fail_commit:
            raise SyncCommitFailed()
        self.rows[cognito_sub] = updated
        return updated


class FakeCognito:
    """Doble de CognitoGateway. Por defecto toda llamada falla con 503 para que
    una prueba que no configuró Cognito nunca obtenga un éxito accidental."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.sign_up_result: SignUpResult | ApiError | None = None
        self.confirm_error: ApiError | None = None
        self.auth_results: list[AuthOutcome | ApiError] = []
        self.update_error: ApiError | None = None
        self.update_errors: list[ApiError | None] = []
        self.user_attributes: dict[str, str] | ApiError | None = None

    def _record(self, name: str, **kwargs: Any) -> None:
        self.calls.append((name, kwargs))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def sign_up(self, email: str, password: str, full_name: str, dpi: str) -> SignUpResult:
        self._record("sign_up", email=email, full_name=full_name, dpi=dpi)
        result = self.sign_up_result
        if isinstance(result, ApiError):
            raise result
        if result is None:
            raise ServiceUnavailableError()
        return result

    def confirm_sign_up(self, email: str, code: str) -> None:
        self._record("confirm_sign_up", email=email)
        if self.confirm_error is not None:
            raise self.confirm_error

    def password_auth(self, email: str, password: str, *, reauthentication: bool = False) -> AuthOutcome:
        self._record("password_auth", email=email, reauthentication=reauthentication)
        if not self.auth_results:
            raise ServiceUnavailableError()
        result = self.auth_results.pop(0)
        if isinstance(result, ApiError):
            raise result
        return result

    def update_attributes(self, access_token: str, *, full_name: str | None = None, dpi: str | None = None) -> None:
        self._record("update_attributes", access_token=access_token, full_name=full_name, dpi=dpi)
        error = self.update_errors.pop(0) if self.update_errors else self.update_error
        if error is not None:
            raise error

    def get_user_attributes(self, access_token: str) -> dict[str, str]:
        self._record("get_user_attributes", access_token=access_token)
        result = self.user_attributes
        if isinstance(result, ApiError):
            raise result
        if result is None:
            raise ServiceUnavailableError()
        return result


class FakeImageObjects:
    """Doble de ImageObjects: ``objects`` es el contenido del bucket."""

    def __init__(self, objects: dict[str, ObjectInfo] | None = None) -> None:
        self.objects = dict(objects or {})
        self.heads: list[str] = []
        self.error: ApiError | None = None

    def head(self, key: str) -> ObjectInfo | None:
        self.heads.append(key)
        if self.error is not None:
            raise self.error
        return self.objects.get(key)


def tokens(access_token: str) -> AuthTokens:
    return AuthTokens(access_token=access_token, id_token="id-token", refresh_token="refresh-token", expires_in=3600)


def challenge(name: str = "NEW_PASSWORD_REQUIRED") -> AuthChallenge:
    return AuthChallenge(name=name, session="s" * 40, parameters={"requiredAttributes": "[]"})


def format_cursor_at(moment: datetime) -> str:
    """Igual que to_char(... 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') de PostgreSQL."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class InMemoryFriendsRepository:
    """Implementa el Protocol de ``app/modules/social/repository.py`` en memoria
    con las mismas reglas que PostgreSQL: un único pendiente por par (en ambas
    direcciones), ``friendships`` con orden canónico y clave única, y
    ``PATCH`` serializado como ``FOR UPDATE``. Solo para pruebas.

    Límite: no reproduce la ventana residual entre una creación y una
    aceptación simultáneas (se verifica solo con RDS real).
    """

    def __init__(self, users: InMemoryUsersRepository) -> None:
        self.users = users
        self.requests: dict[str, dict[str, Any]] = {}
        self.friendships: dict[tuple[str, str], str | None] = {}  # (low, high) -> request_id
        self.fail_with: Exception | None = None
        self._lock = threading.Lock()
        self._ticks = 0

    # -- utilidades ------------------------------------------------------------

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def _by_id(self, user_id: str) -> UserRecord | None:
        return next((row for row in self.users.rows.values() if row.id == user_id), None)

    def _public(self, user_id: str) -> PublicUserRecord:
        row = self._by_id(user_id)
        assert row is not None, "usuario inexistente en el doble"
        return PublicUserRecord(row.id, row.full_name, row.profile_image_key)

    @staticmethod
    def _pair(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a < b else (b, a)

    def _record(self, request_id: str) -> RequestRecord:
        data = self.requests[request_id]
        return RequestRecord(
            id=request_id,
            status=data["status"],
            created_at=data["created_at"],
            requester=self._public(data["requester"]),
            addressee=self._public(data["addressee"]),
        )

    def friend_ids(self, user_id: str) -> set[str]:
        return {b if a == user_id else a for a, b in self.friendships if user_id in (a, b)}

    # -- Protocol --------------------------------------------------------------

    def list_non_friends(self, me_id: str, after: CursorPosition | None, limit: int) -> list[PersonRow]:
        self._check()
        friends = self.friend_ids(me_id)
        rows = [
            PersonRow(
                user=PublicUserRecord(r.id, r.full_name, r.profile_image_key),
                cursor_at=format_cursor_at(self.users.created[r.id]),
            )
            for r in self.users.rows.values()
            if r.id != me_id and r.profile_image_key is not None and r.id not in friends
        ]
        rows.sort(key=lambda row: (row.cursor_at, row.user.id), reverse=True)
        if after is not None:
            rows = [row for row in rows if (row.cursor_at, row.user.id) < (after.created_at, after.user_id)]
        return rows[:limit]

    def list_requests(self, me_id: str) -> list[RequestRecord]:
        self._check()
        ids = [
            rid
            for rid, data in self.requests.items()
            if data["status"] == "pending" and me_id in (data["requester"], data["addressee"])
        ]
        ids.sort(key=lambda rid: (self.requests[rid]["created_at"], rid), reverse=True)
        return [self._record(rid) for rid in ids]

    def list_friends(self, me_id: str) -> list[PublicUserRecord]:
        self._check()
        people = [self._public(fid) for fid in self.friend_ids(me_id)]
        return sorted(people, key=lambda p: (p.full_name, p.id))

    def create_request(self, requester_id: str, addressee_id: str) -> RequestRecord:
        self._check()
        addressee = self._by_id(addressee_id)
        if addressee is None or addressee.profile_image_key is None:
            raise AddresseeNotFound()
        if self._pair(requester_id, addressee_id) in self.friendships:
            raise AlreadyFriends()
        for data in self.requests.values():
            if data["status"] == "pending" and {data["requester"], data["addressee"]} == {requester_id, addressee_id}:
                raise RequestPending()
        self._ticks += 1
        request_id = str(uuid.uuid4())
        self.requests[request_id] = {
            "requester": requester_id,
            "addressee": addressee_id,
            "status": "pending",
            "created_at": CLOCK_START + timedelta(minutes=self._ticks, microseconds=987),
        }
        return self._record(request_id)

    def answer_request(
        self, request_id: str, responder_id: str, decision: Literal["accepted", "rejected"]
    ) -> RequestRecord:
        self._check()
        with self._lock:  # FOR UPDATE: la segunda respuesta espera y ve el estado final
            data = self.requests.get(request_id)
            if data is None:
                raise RequestNotFound()
            if data["addressee"] != responder_id:
                raise NotAddressee()
            if data["status"] != "pending":
                raise AlreadyAnswered()
            pair = self._pair(data["requester"], data["addressee"])
            if decision == "accepted" and pair in self.friendships:
                raise AlreadyFriends()
            data["status"] = decision
            if decision == "accepted":
                self.friendships[pair] = request_id
            return self._record(request_id)


class FakeSqlConnection:
    """Conexión psycopg falsa con ``fetchone`` y ``fetchall``.

    ``results`` es una cola con una entrada por ``execute``: una lista de filas
    (``fetchall`` las devuelve; ``fetchone`` la primera o ``None``), ``None``
    (sin filas) o una excepción, que se lanza en ese ``execute``.
    """

    def __init__(self, results: list[Any] | None = None, *, commit_error: Exception | None = None) -> None:
        self.results = list(results or [])
        self.commit_error = commit_error
        self.statements: list[tuple[str, Any]] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, sql: str, params: Any = None) -> Any:
        self.statements.append((sql, params))
        entry = self.results.pop(0) if self.results else None
        if isinstance(entry, BaseException):
            raise entry
        rows = list(entry or [])
        return SimpleNamespace(fetchone=lambda: rows[0] if rows else None, fetchall=lambda: rows)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.rolled_back = True
            raise
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True


class FakeSqlDatabase:
    def __init__(self, connection: FakeSqlConnection) -> None:
        self.conn = connection

    @contextmanager
    def connection(self) -> Iterator[FakeSqlConnection]:
        yield self.conn
