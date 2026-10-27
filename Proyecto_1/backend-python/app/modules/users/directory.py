"""Servicios compartidos por /auth/* y /me sobre la tabla ``users``.

- ``call``: ejecuta una operación de RDS y convierte fallas inesperadas en 503
  (nunca respaldo en memoria); deja pasar errores de negocio.
- ``get_or_reconcile``: si un usuario autenticado no tiene fila en RDS (por
  ejemplo, el INSERT falló después de SignUp), la recrea con los atributos de
  Cognito (``GetUser`` con su propio access token). Con cliente público no
  existe AdminDeleteUser, así que se repara en vez de compensar.
- ``verify_issued``: verifica la firma y claims de un access token recién
  emitido por Cognito antes de confiar en su ``sub``.
- ``profile_payload``: esquema ``Profile`` de openapi.yaml.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import quote

from app.common.auth import CognitoTokenVerifier, KeySourceUnavailable, Principal, TokenInvalid
from app.common.errors import ApiError, ServiceUnavailableError
from app.config import S3Settings
from app.modules.users.repository import (
    DuplicateUser,
    InvalidUserData,
    SyncCommitFailed,
    UserRecord,
    UsersRepository,
)

logger = logging.getLogger("semisocial.users")

T = TypeVar("T")

_DPI_RE = re.compile(r"^[0-9]{13}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_CONFLICT_MESSAGES = {
    "email": ("Ya existe una cuenta con ese correo.", "EMAIL_TAKEN"),
    "dpi": ("Ya existe una cuenta con ese DPI.", "DPI_TAKEN"),
}


def conflict_error(field: str) -> ApiError:
    message, reason = _CONFLICT_MESSAGES.get(field, ("La cuenta ya existe.", "ACCOUNT_EXISTS"))
    return ApiError(409, "CONFLICT", message, details={"reason": reason})


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log estructurado sin PII: solo campos permitidos por JsonFormatter."""
    logger.log(level, event, extra={"event": event, **fields})


class UserDirectory:
    def __init__(
        self,
        users: UsersRepository,
        cognito: Any,
        verifier: CognitoTokenVerifier,
        s3: S3Settings,
    ) -> None:
        self.users = users
        self.cognito = cognito
        self._verifier = verifier
        self._s3 = s3

    def call(self, operation: Callable[[], T]) -> T:
        try:
            return operation()
        except (ApiError, DuplicateUser, InvalidUserData, SyncCommitFailed):
            raise
        except Exception as exc:  # noqa: BLE001
            # psycopg/pool: el mensaje puede contener datos de conexión; solo el tipo.
            log_event("users.db_error", logging.ERROR, errorType=type(exc).__name__)
            raise ServiceUnavailableError() from None

    def verify_issued(self, access_token: str) -> Principal:
        try:
            return self._verifier.verify(access_token)
        except (TokenInvalid, KeySourceUnavailable) as exc:
            # Cognito acaba de emitirlo: si no verifica, la configuración (pool,
            # cliente, JWKS) no coincide o no hay salida al JWKS.
            log_event("auth.issued_token_rejected", logging.ERROR, errorType=type(exc).__name__)
            raise ServiceUnavailableError() from None

    def get_or_reconcile(self, sub: str, access_token: str) -> UserRecord:
        record = self.call(lambda: self.users.get_by_sub(sub))
        if record is not None:
            return record

        attributes = self.cognito.get_user_attributes(access_token)
        email = (attributes.get("email") or "").strip().lower()
        full_name = (attributes.get("name") or "").strip()
        dpi = (attributes.get("custom:dpi") or "").strip()
        if attributes.get("sub") != sub:
            log_event("users.reconcile_failed", logging.ERROR, reason="SUB_MISMATCH", cognitoSub=sub)
            raise ServiceUnavailableError()
        if not (_EMAIL_RE.match(email) and 2 <= len(full_name) <= 160 and _DPI_RE.match(dpi)):
            log_event("users.reconcile_failed", logging.ERROR, reason="INVALID_COGNITO_ATTRIBUTES", cognitoSub=sub)
            raise ServiceUnavailableError()

        try:
            record = self.call(lambda: self.users.insert(cognito_sub=sub, email=email, full_name=full_name, dpi=dpi))
        except DuplicateUser as exc:
            if exc.field == "cognito_sub":  # otra solicitud la creó en paralelo
                existing = self.call(lambda: self.users.get_by_sub(sub))
                if existing is not None:
                    return existing
            log_event("users.reconcile_failed", logging.ERROR, reason="DUPLICATE_" + exc.field.upper(), cognitoSub=sub)
            raise conflict_error(exc.field) from None
        except InvalidUserData:
            log_event("users.reconcile_failed", logging.ERROR, reason="INVALID_COGNITO_ATTRIBUTES", cognitoSub=sub)
            raise ServiceUnavailableError() from None
        log_event("users.reconciled", logging.WARNING, cognitoSub=sub)
        return record

    def image_url(self, key: str | None) -> str | None:
        if not key:
            return None
        return f"https://{self._s3.images_bucket}.s3.{self._s3.region}.amazonaws.com/{quote(key, safe='/')}"

    def profile_payload(self, record: UserRecord) -> dict[str, Any]:
        return {
            "userId": record.id,
            "fullName": record.full_name,
            "email": record.email,
            "dpi": record.dpi,
            "profileImageUrl": self.image_url(record.profile_image_key),
            "profileComplete": record.profile_complete,
        }
