"""Acceso a la tabla ``users`` (database/migrations/001_core_schema.sql).

- ``profileComplete`` = ``profile_image_key IS NOT NULL`` (docs/data-model/model.md).
- Sin respaldo en memoria: si RDS falla, la excepción llega al servicio, que
  responde 503. El único repositorio en memoria vive en las pruebas.
- Las restricciones UNIQUE (email, dpi, cognito_sub) se traducen a
  ``DuplicateUser`` para responder 409; las CHECK a ``InvalidUserData``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg

from app.common.errors import ServiceUnavailableError

_COLUMNS = "id::text, cognito_sub, email::text, full_name, dpi, profile_image_key, face_reference_key"

# Nombres por defecto de PostgreSQL para UNIQUE de columna (tabla_columna_key).
_UNIQUE_FIELDS = {
    "users_email_key": "email",
    "users_dpi_key": "dpi",
    "users_cognito_sub_key": "cognito_sub",
}


@dataclass(frozen=True)
class UserRecord:
    id: str
    cognito_sub: str
    email: str
    full_name: str
    dpi: str
    profile_image_key: str | None
    face_reference_key: str | None

    @property
    def profile_complete(self) -> bool:
        return self.profile_image_key is not None


@dataclass(frozen=True)
class ProfileChanges:
    full_name: str | None = None
    dpi: str | None = None
    profile_image_key: str | None = None
    face_reference_key: str | None = None


class DuplicateUser(Exception):
    """Violación de UNIQUE; ``field`` es ``email``, ``dpi`` o ``cognito_sub``."""

    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


class InvalidUserData(Exception):
    """Violación de una restricción CHECK (formato rechazado por la BD)."""


class SyncCommitFailed(Exception):
    """El COMMIT falló después de sincronizar un sistema externo (Cognito)."""


class UsersRepository(Protocol):
    def profile_complete(self, cognito_sub: str) -> bool | None: ...

    def get_by_sub(self, cognito_sub: str) -> UserRecord | None: ...

    def find_conflicts(
        self, *, email: str | None = None, dpi: str | None = None, exclude_sub: str | None = None
    ) -> list[str]:
        """Campos (``email``, ``dpi``) ya usados por OTRO usuario, en ese orden."""

    def insert(self, *, cognito_sub: str, email: str, full_name: str, dpi: str) -> UserRecord: ...

    def complete_profile(self, cognito_sub: str, profile_image_key: str, face_reference_key: str) -> UserRecord | None:
        """Fija foto y referencia solo si el perfil sigue incompleto; ``None`` si no aplicó."""

    def update_profile(
        self, cognito_sub: str, changes: ProfileChanges, before_commit: Callable[[], None]
    ) -> UserRecord | None:
        """UPDATE en una transacción; ``before_commit`` corre antes del COMMIT y,
        si lanza, se hace ROLLBACK. Si el COMMIT falla después de ejecutar
        ``before_commit`` se lanza ``SyncCommitFailed``."""


def _record(row: Any) -> UserRecord:
    return UserRecord(*row)


def _duplicate_field(exc: psycopg.errors.UniqueViolation) -> str:
    constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
    return _UNIQUE_FIELDS.get(constraint or "", "unknown")


class PostgresUsersRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def profile_complete(self, cognito_sub: str) -> bool | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT profile_image_key IS NOT NULL FROM users WHERE cognito_sub = %s",
                (cognito_sub,),
            ).fetchone()
        return None if row is None else bool(row[0])

    def get_by_sub(self, cognito_sub: str) -> UserRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(f"SELECT {_COLUMNS} FROM users WHERE cognito_sub = %s", (cognito_sub,)).fetchone()
        return None if row is None else _record(row)

    def find_conflicts(
        self, *, email: str | None = None, dpi: str | None = None, exclude_sub: str | None = None
    ) -> list[str]:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT"
                " EXISTS (SELECT 1 FROM users WHERE email = %(email)s::citext"
                "         AND cognito_sub IS DISTINCT FROM %(exclude)s::varchar),"
                " EXISTS (SELECT 1 FROM users WHERE dpi = %(dpi)s::varchar"
                "         AND cognito_sub IS DISTINCT FROM %(exclude)s::varchar)",
                {"email": email, "dpi": dpi, "exclude": exclude_sub},
            ).fetchone()
        email_taken, dpi_taken = bool(row[0]), bool(row[1])
        return [name for name, taken in (("email", email_taken), ("dpi", dpi_taken)) if taken]

    def insert(self, *, cognito_sub: str, email: str, full_name: str, dpi: str) -> UserRecord:
        try:
            with self._db.connection() as conn:
                row = conn.execute(
                    f"INSERT INTO users (cognito_sub, email, full_name, dpi) VALUES (%s, %s, %s, %s) RETURNING {_COLUMNS}",
                    (cognito_sub, email, full_name, dpi),
                ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise DuplicateUser(_duplicate_field(exc)) from None
        except psycopg.errors.CheckViolation:
            raise InvalidUserData() from None
        return _record(row)

    def complete_profile(self, cognito_sub: str, profile_image_key: str, face_reference_key: str) -> UserRecord | None:
        try:
            with self._db.connection() as conn:
                row = conn.execute(
                    "UPDATE users SET profile_image_key = %s, face_reference_key = %s"
                    f" WHERE cognito_sub = %s AND profile_image_key IS NULL RETURNING {_COLUMNS}",
                    (profile_image_key, face_reference_key, cognito_sub),
                ).fetchone()
        except psycopg.errors.CheckViolation:
            raise InvalidUserData() from None
        return None if row is None else _record(row)

    def update_profile(
        self, cognito_sub: str, changes: ProfileChanges, before_commit: Callable[[], None]
    ) -> UserRecord | None:
        synced = False
        try:
            with self._db.connection() as conn:
                with conn.transaction():
                    row = conn.execute(
                        "UPDATE users SET"
                        " full_name = COALESCE(%(full_name)s::varchar, full_name),"
                        " dpi = COALESCE(%(dpi)s::varchar, dpi),"
                        " profile_image_key = COALESCE(%(image)s::text, profile_image_key),"
                        " face_reference_key = COALESCE(%(reference)s::text, face_reference_key)"
                        f" WHERE cognito_sub = %(sub)s RETURNING {_COLUMNS}",
                        {
                            "full_name": changes.full_name,
                            "dpi": changes.dpi,
                            "image": changes.profile_image_key,
                            "reference": changes.face_reference_key,
                            "sub": cognito_sub,
                        },
                    ).fetchone()
                    if row is None:
                        return None
                    before_commit()
                    synced = True
        except psycopg.errors.UniqueViolation as exc:
            raise DuplicateUser(_duplicate_field(exc)) from None
        except psycopg.errors.CheckViolation:
            raise InvalidUserData() from None
        except psycopg.Error:
            if synced:
                raise SyncCommitFailed() from None
            raise
        return _record(row)


class UnavailableUsersRepository:
    """Sin RDS configurado: toda consulta de perfil responde 503 (nunca memoria)."""

    def profile_complete(self, cognito_sub: str) -> bool | None:
        raise ServiceUnavailableError()

    def get_by_sub(self, cognito_sub: str) -> UserRecord | None:
        raise ServiceUnavailableError()

    def find_conflicts(
        self, *, email: str | None = None, dpi: str | None = None, exclude_sub: str | None = None
    ) -> list[str]:
        raise ServiceUnavailableError()

    def insert(self, *, cognito_sub: str, email: str, full_name: str, dpi: str) -> UserRecord:
        raise ServiceUnavailableError()

    def complete_profile(self, cognito_sub: str, profile_image_key: str, face_reference_key: str) -> UserRecord | None:
        raise ServiceUnavailableError()

    def update_profile(
        self, cognito_sub: str, changes: ProfileChanges, before_commit: Callable[[], None]
    ) -> UserRecord | None:
        raise ServiceUnavailableError()


class MockUsersRepository(UnavailableUsersRepository):
    """Solo APP_ENV=local con MOCK_MODE=true y sin RDS: todo usuario autenticado
    se considera completo (para probar Translate/Lex). No guarda perfiles: las
    rutas de /auth y /me responden 503."""

    def profile_complete(self, cognito_sub: str) -> bool | None:
        return True
