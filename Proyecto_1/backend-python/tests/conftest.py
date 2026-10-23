"""Fixtures comunes: llaves RSA de prueba, emisión de tokens y app con dobles.

Las llaves se generan en memoria en cada sesión; nunca se escriben a disco.
"""

from __future__ import annotations

import io
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.auth import CognitoTokenVerifier, static_key_resolver
from app.common.logs import build_handler
from app.config import Settings
from app.main import create_app
from app.modules.integrations.lex.service import BotService
from app.modules.integrations.translate.service import TranslationService
from tests.fakes import FakeCognito, FakeImageObjects, InMemoryFriendsRepository, InMemoryUsersRepository

POOL_ID = "us-east-1_testPool"
ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{POOL_ID}"
CLIENT_ID = "test-client-id"
COMPLETE_SUB = "11111111-1111-4111-8111-111111111111"
INCOMPLETE_SUB = "22222222-2222-4222-8222-222222222222"
UNKNOWN_SUB = "33333333-3333-4333-8333-333333333333"


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def public_pem(rsa_key: rsa.RSAPrivateKey) -> bytes:
    return rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def build_claims(sub: str = COMPLETE_SUB, **overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "scope": "aws.cognito.signin.user.admin",
        "username": sub,
        "iat": now,
        "exp": now + 600,
        "jti": str(uuid.uuid4()),
    }
    for key, value in overrides.items():
        if value is None:
            claims.pop(key, None)
        else:
            claims[key] = value
    return claims


@pytest.fixture(scope="session")
def make_token(rsa_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    def _make(sub: str = COMPLETE_SUB, *, key: Any = None, kid: str = "test-kid", **overrides: Any) -> str:
        return jwt.encode(
            build_claims(sub, **overrides), key or rsa_key, algorithm="RS256", headers={"kid": kid}
        )

    return _make


class FakeDatabase:
    def __init__(self, *, configured: bool = True, healthy: bool = True) -> None:
        self.configured = configured
        self.healthy = healthy
        self.opened_with: bool | None = None
        self.closed = False

    def open(self, *, required: bool) -> None:
        self.opened_with = required

    def close(self) -> None:
        self.closed = True

    def ping(self) -> bool:
        return self.healthy


COMPLETE_EMAIL = "completo@example.com"
COMPLETE_DPI = "1111111111111"
INCOMPLETE_EMAIL = "incompleto@example.com"
INCOMPLETE_DPI = "2222222222222"


def seeded_users() -> InMemoryUsersRepository:
    """COMPLETE_SUB con foto, INCOMPLETE_SUB sin foto, UNKNOWN_SUB sin fila."""
    users = InMemoryUsersRepository()
    users.add(COMPLETE_SUB, email=COMPLETE_EMAIL, full_name="Ana Completa", dpi=COMPLETE_DPI, complete=True)
    users.add(INCOMPLETE_SUB, email=INCOMPLETE_EMAIL, full_name="Bruno Incompleto", dpi=INCOMPLETE_DPI, complete=False)
    return users


def _no_real_aws() -> Any:
    raise AssertionError("Las pruebas no deben crear un cliente AWS real; inyecte translation_service")


def local_settings(**env: str) -> Settings:
    base = {"APP_ENV": "local", "COGNITO_USER_POOL_ID": POOL_ID, "COGNITO_APP_CLIENT_ID": CLIENT_ID}
    base.update(env)
    return Settings.from_env(base)


@pytest.fixture
def build_app(public_pem: bytes) -> Callable[..., FastAPI]:
    def _build(database: FakeDatabase | None = None, **kwargs: Any) -> FastAPI:
        users = kwargs.pop("users_repository", None) or seeded_users()
        return create_app(
            kwargs.pop("settings", None) or local_settings(),
            database=database or FakeDatabase(),
            verifier=kwargs.pop(
                "verifier", CognitoTokenVerifier(ISSUER, CLIENT_ID, static_key_resolver(public_pem))
            ),
            users_repository=users,
            friends_repository=kwargs.pop("friends_repository", None) or InMemoryFriendsRepository(users),
            # Dobles de Cognito y S3: sin configurar, toda llamada responde 503.
            cognito_gateway=kwargs.pop("cognito_gateway", None) or FakeCognito(),
            image_objects=kwargs.pop("image_objects", None) or FakeImageObjects(),
            translation_service=kwargs.pop("translation_service", TranslationService(_no_real_aws)),
            # Sin LEX_BOT_ID/LEX_BOT_ALIAS_ID: /bot/messages responde 503 sin crear cliente.
            bot_service=kwargs.pop("bot_service", BotService(local_settings().lex, _no_real_aws)),
        )

    return _build


@pytest.fixture
def client(build_app: Callable[..., FastAPI]) -> Iterator[TestClient]:
    with TestClient(build_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_header(make_token: Callable[..., str]) -> Callable[..., dict[str, str]]:
    def _header(sub: str = COMPLETE_SUB, **overrides: Any) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(sub, **overrides)}"}

    return _header


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    """Captura los logs JSON (con el filtro de redacción real) de la prueba."""
    stream = io.StringIO()
    handler = build_handler(stream)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


@contextmanager
def running(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def assert_error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "requestId", "details"}
    assert body["code"] == code
    assert isinstance(body["message"], str) and body["message"]
    assert body["requestId"] == response.headers["x-request-id"]
    return body
