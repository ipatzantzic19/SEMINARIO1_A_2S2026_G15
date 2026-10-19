"""Dobles de prueba de RDS, Cognito y S3 (solo pruebas; la app nunca usa memoria)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.cognito.gateway import AuthChallenge, AuthOutcome, AuthTokens, SignUpResult
from app.modules.integrations.s3.objects import ObjectInfo
from app.modules.users.repository import DuplicateUser, ProfileChanges, SyncCommitFailed, UserRecord


class InMemoryUsersRepository:
    """Implementa el Protocol de ``app/modules/users/repository.py`` en memoria,
    con las mismas reglas UNIQUE y de transacción que PostgreSQL."""

    def __init__(self) -> None:
        self.rows: dict[str, UserRecord] = {}
        self.fail_with: Exception | None = None  # simula RDS caído en cualquier llamada
        self.fail_commit = False  # simula COMMIT fallido tras before_commit

    def add(self, sub: str, *, email: str, full_name: str, dpi: str, complete: bool) -> UserRecord:
        record = UserRecord(
            id=str(uuid.uuid4()),
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
