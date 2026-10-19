"""Registro, confirmación y login con Cognito (PRO-14).

Orden del registro (docs/api/python-auth.md §3):
1. RDS: correo o DPI ya usados → 409 sin tocar Cognito (Cognito no conoce el DPI).
2. Cognito SignUp.
3. INSERT en ``users`` con el ``UserSub``. Si falla, el usuario queda sin
   confirmar en Cognito y sin fila: se registra el ``sub`` y la fila se recrea
   en el primer login o ``GET /me`` (``UserDirectory.get_or_reconcile``).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.cognito.gateway import MSG_PASSWORD_POLICY, AuthChallenge
from app.modules.users.directory import UserDirectory, conflict_error, log_event
from app.modules.users.repository import DuplicateUser, InvalidUserData

# Política del User Pool (infra/cognito/user-pool.yaml): 12 caracteres con
# minúscula, mayúscula, número y símbolo. SignUp exige además ``[\S]+`` (sin
# espacios) y un máximo de 256 caracteres (API_SignUp, parámetro Password).
_SYMBOLS = re.escape("^$*.[]{}()?\"!@#%&/\\,><':;|_~`=+-")
_PASSWORD_RULES = (
    re.compile(r"^\S{12,256}$"),
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"[0-9]"),
    re.compile(f"[{_SYMBOLS}]"),
)


def password_meets_policy(password: str) -> bool:
    return all(rule.search(password) for rule in _PASSWORD_RULES)


class AuthService:
    def __init__(self, directory: UserDirectory) -> None:
        self._directory = directory
        self._users = directory.users
        self._cognito = directory.cognito

    def register(self, *, email: str, password: str, full_name: str, dpi: str) -> dict[str, Any]:
        if not password_meets_policy(password):
            raise ApiError(400, "VALIDATION_ERROR", MSG_PASSWORD_POLICY, details={"reason": "PASSWORD_POLICY"})

        conflicts = self._directory.call(lambda: self._users.find_conflicts(email=email, dpi=dpi))
        if conflicts:
            raise conflict_error(conflicts[0])

        result = self._cognito.sign_up(email, password, full_name, dpi)

        try:
            record = self._directory.call(
                lambda: self._users.insert(cognito_sub=result.sub, email=email, full_name=full_name, dpi=dpi)
            )
        except DuplicateUser as exc:
            # Carrera con otro registro entre la comprobación y el INSERT.
            log_event("auth.register_orphan", logging.ERROR, reason="DUPLICATE_" + exc.field.upper(), cognitoSub=result.sub)
            raise conflict_error(exc.field) from None
        except InvalidUserData:
            log_event("auth.register_orphan", logging.ERROR, reason="INVALID_DATA", cognitoSub=result.sub)
            raise ApiError(400, "VALIDATION_ERROR") from None
        except ServiceUnavailableError:
            log_event("auth.register_orphan", logging.ERROR, reason="DB_UNAVAILABLE", cognitoSub=result.sub)
            raise

        log_event("auth.registered")
        return {
            "userId": record.id,
            "email": record.email,
            "confirmationRequired": not result.confirmed,
            "profileComplete": False,
        }

    def confirm(self, *, email: str, code: str) -> None:
        self._cognito.confirm_sign_up(email, code)
        log_event("auth.confirmed")

    def login(self, *, email: str, password: str) -> tuple[int, dict[str, Any]]:
        outcome = self._cognito.password_auth(email, password)
        if isinstance(outcome, AuthChallenge):
            log_event("auth.login_challenge", reason=outcome.name)
            return 202, {"challenge": outcome.name, "session": outcome.session, "parameters": outcome.parameters}

        principal = self._directory.verify_issued(outcome.access_token)
        record = self._directory.get_or_reconcile(principal.sub, outcome.access_token)
        log_event("auth.login")
        return 200, {
            "accessToken": outcome.access_token,
            "idToken": outcome.id_token,
            "refreshToken": outcome.refresh_token,
            "expiresIn": outcome.expires_in,
            "tokenType": "Bearer",
            "profileComplete": record.profile_complete,
        }
