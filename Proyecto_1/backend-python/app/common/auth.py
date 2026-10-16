"""Validación de access tokens de Cognito como dependencias reutilizables.

Se verifica SIEMPRE: firma RS256 (JWKS de Cognito o, solo en local, una llave
pública configurada), ``iss``, ``token_use=access``, ``client_id`` y ``exp``.
Nunca se acepta un token sin verificar, tampoco en modo local.

- 401 UNAUTHENTICATED: token ausente, malformado, vencido o inválido.
- 403 FORBIDDEN: token válido pero el perfil está incompleto o no existe en RDS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.errors import ForbiddenError, ServiceUnavailableError, UnauthenticatedError
from app.config import CognitoSettings

logger = logging.getLogger("semisocial.auth")

ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "iat", "iss", "sub", "token_use", "client_id"]

KeyResolver = Callable[[str], Any]


@dataclass(frozen=True)
class Principal:
    """Identidad autenticada. ``sub`` corresponde a ``users.cognito_sub``."""

    sub: str
    username: str | None
    client_id: str
    scopes: tuple[str, ...]


class TokenInvalid(Exception):
    """Token rechazado (el motivo es solo para pruebas; no se registra el token)."""


class KeySourceUnavailable(Exception):
    """No se pudo obtener el JWKS (Cognito inalcanzable)."""


def jwks_key_resolver(jwks_uri: str) -> KeyResolver:
    client = jwt.PyJWKClient(jwks_uri, cache_keys=True, lifespan=3600, timeout=5)

    def resolve(token: str) -> Any:
        try:
            return client.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as exc:
            raise KeySourceUnavailable() from exc
        except (jwt.PyJWKClientError, jwt.DecodeError) as exc:
            raise TokenInvalid("kid desconocido o JWKS inválido") from exc

    return resolve


def static_key_resolver(public_key_pem: bytes) -> KeyResolver:
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    key = load_pem_public_key(public_key_pem)

    def resolve(_token: str) -> Any:
        return key

    return resolve


def _no_key_resolver(_token: str) -> Any:
    raise TokenInvalid("sin llave configurada")


class CognitoTokenVerifier:
    def __init__(self, issuer: str, client_id: str, key_resolver: KeyResolver, leeway_seconds: int = 0) -> None:
        self._issuer = issuer
        self._client_id = client_id
        self._resolve_key = key_resolver
        self._leeway = leeway_seconds

    def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenInvalid("token malformado") from exc
        if header.get("alg") not in ALGORITHMS:
            raise TokenInvalid("algoritmo no permitido")

        key = self._resolve_key(token)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": REQUIRED_CLAIMS, "verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            raise TokenInvalid(type(exc).__name__) from exc

        # Los access tokens de Cognito no traen "aud"; el cliente va en "client_id".
        if claims.get("token_use") != "access":
            raise TokenInvalid("token_use distinto de access")
        if claims.get("client_id") != self._client_id:
            raise TokenInvalid("client_id no coincide")

        return Principal(
            sub=str(claims["sub"]),
            username=claims.get("username"),
            client_id=str(claims["client_id"]),
            scopes=tuple(str(claims.get("scope", "")).split()),
        )


def build_verifier(settings: CognitoSettings, *, production: bool) -> CognitoTokenVerifier:
    if settings.local_public_key_file is not None and not production:
        resolver = static_key_resolver(Path(settings.local_public_key_file).read_bytes())
        logger.warning("Auth en modo local: tokens verificados con AUTH_LOCAL_PUBLIC_KEY_FILE.")
    elif settings.jwks_uri:
        resolver = jwks_key_resolver(settings.jwks_uri)
    else:  # pragma: no cover - la configuración siempre deriva jwks_uri
        resolver = _no_key_resolver
    return CognitoTokenVerifier(settings.issuer, settings.app_client_id, resolver)


# --------------------------------------------------------------------------
# Estado del perfil en RDS
# --------------------------------------------------------------------------


class UsersRepository(Protocol):
    def profile_complete(self, cognito_sub: str) -> bool | None:
        """True/False según ``users.profile_image_key``; None si no existe."""


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


class MockUsersRepository:
    """Solo APP_ENV=local con MOCK_MODE=true: todo usuario autenticado está completo."""

    def profile_complete(self, cognito_sub: str) -> bool | None:
        return True


class UnavailableUsersRepository:
    def profile_complete(self, cognito_sub: str) -> bool | None:
        raise ServiceUnavailableError()


# --------------------------------------------------------------------------
# Dependencias FastAPI
# --------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False, description="Access token de Cognito")


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise UnauthenticatedError()
    verifier: CognitoTokenVerifier = request.app.state.verifier
    try:
        principal = verifier.verify(credentials.credentials)
    except TokenInvalid as exc:
        logger.info("Token rechazado: %s", exc)
        raise UnauthenticatedError() from None
    except KeySourceUnavailable:
        logger.error("No fue posible obtener el JWKS de Cognito.")
        raise ServiceUnavailableError() from None
    request.state.principal = principal
    return principal


def require_complete_profile(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    users: UsersRepository = request.app.state.users_repository
    try:
        complete = users.profile_complete(principal.sub)
    except ServiceUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Error consultando el perfil: %s", type(exc).__name__)
        raise ServiceUnavailableError() from None
    if not complete:
        raise ForbiddenError(
            "Complete su perfil para usar esta funcionalidad.",
            details={"reason": "PROFILE_INCOMPLETE"},
        )
    return principal
