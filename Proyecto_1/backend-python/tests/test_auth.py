"""Validación de JWT de Cognito con un par de llaves RSA de prueba."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.common.auth import CognitoTokenVerifier, KeySourceUnavailable, TokenInvalid, jwks_key_resolver
from tests.conftest import (
    CLIENT_ID,
    COMPLETE_SUB,
    INCOMPLETE_SUB,
    ISSUER,
    UNKNOWN_SUB,
    assert_error,
    build_claims,
    running,
)


def test_missing_token_is_401(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert_error(response, 401, "UNAUTHENTICATED")
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer ", "token abc", "Bearer no.es.jwt"])
def test_malformed_authorization_is_401(client: TestClient, header: str) -> None:
    assert_error(client.get("/api/v1/me", headers={"Authorization": header}), 401, "UNAUTHENTICATED")


def test_valid_access_token_passes_auth(client: TestClient, auth_header) -> None:
    # /me exige solo token válido (PRO-14).
    response = client.get("/api/v1/me", headers=auth_header())
    assert response.status_code == 200
    assert response.json()["profileComplete"] is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_otherPool"},
        {"client_id": "otro-cliente"},
        {"token_use": "id"},
        {"exp": int(time.time()) - 10},
        {"exp": None},
        {"sub": None},
        {"token_use": None},
        {"client_id": None},
    ],
    ids=["issuer", "client_id", "id-token", "expired", "no-exp", "no-sub", "no-token_use", "no-client_id"],
)
def test_invalid_claims_are_401(client: TestClient, make_token, overrides: dict[str, Any]) -> None:
    token = make_token(**overrides)
    assert_error(client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}), 401, "UNAUTHENTICATED")


def test_wrong_signature_is_401(client: TestClient, make_token) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(key=other_key)
    assert_error(client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}), 401, "UNAUTHENTICATED")


def test_tampered_payload_is_401(client: TestClient, make_token) -> None:
    header, _, signature = make_token().split(".")
    forged = base64.urlsafe_b64encode(json.dumps(build_claims(sub=UNKNOWN_SUB)).encode()).rstrip(b"=").decode()
    token = f"{header}.{forged}.{signature}"
    assert_error(client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}), 401, "UNAUTHENTICATED")


def test_symmetric_and_none_algorithms_are_rejected(client: TestClient) -> None:
    hs = jwt.encode(build_claims(), "secreto-compartido-de-prueba-con-32-bytes", algorithm="HS256")
    unsigned = jwt.encode(build_claims(), None, algorithm="none")
    for token in (hs, unsigned):
        assert_error(client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}), 401, "UNAUTHENTICATED")


def test_incomplete_profile_is_403_on_social_routes(client: TestClient, auth_header) -> None:
    body = assert_error(client.get("/api/v1/posts", headers=auth_header(INCOMPLETE_SUB)), 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}
    assert_error(client.get("/api/v1/posts", headers=auth_header(UNKNOWN_SUB)), 403, "FORBIDDEN")


def test_incomplete_profile_can_reach_profile_routes(client: TestClient, auth_header) -> None:
    response = client.post(
        "/api/v1/me/complete-profile",
        json={"profileImageKey": f"Fotos_Perfil/public/{INCOMPLETE_SUB}/a.webp"},
        headers=auth_header(INCOMPLETE_SUB),
    )
    # Llega al handler (no 403): la clave no tiene el formato de la Lambda.
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_IMAGE_KEY"}
    assert client.get("/api/v1/me", headers=auth_header(INCOMPLETE_SUB)).json()["profileComplete"] is False


def test_complete_profile_reaches_pending_social_route(client: TestClient, auth_header) -> None:
    body = assert_error(client.get("/api/v1/posts", headers=auth_header(COMPLETE_SUB)), 501, "NOT_IMPLEMENTED")
    assert body["details"]["ticket"] == "PRO-34"


def test_auth_runs_before_body_validation(client: TestClient) -> None:
    assert_error(client.post("/api/v1/posts", json={}), 401, "UNAUTHENTICATED")


def test_profile_lookup_failure_is_503(build_app, auth_header) -> None:
    class BrokenRepository:
        def profile_complete(self, cognito_sub: str) -> bool | None:
            raise ConnectionError("db caída")

    with running(build_app(users_repository=BrokenRepository())) as test_client:
        assert_error(test_client.get("/api/v1/friends", headers=auth_header()), 503, "SERVICE_UNAVAILABLE")


def test_local_mode_without_key_never_accepts_tokens(build_app, make_token) -> None:
    def no_key(_token: str) -> Any:
        raise TokenInvalid("sin llave")

    app = build_app(verifier=CognitoTokenVerifier(ISSUER, CLIENT_ID, no_key))
    with running(app) as test_client:
        response = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert_error(response, 401, "UNAUTHENTICATED")


# --- Resolución de llaves vía JWKS (como en producción) --------------------


def _jwks_for(key: rsa.RSAPrivateKey, kid: str) -> dict[str, Any]:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def test_jwks_resolver_accepts_known_kid_and_rejects_unknown(monkeypatch, rsa_key, make_token) -> None:
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: _jwks_for(rsa_key, "kid-1"))
    verifier = CognitoTokenVerifier(ISSUER, CLIENT_ID, jwks_key_resolver(f"{ISSUER}/.well-known/jwks.json"))

    principal = verifier.verify(make_token(kid="kid-1"))
    assert principal.sub == COMPLETE_SUB
    assert principal.client_id == CLIENT_ID

    with pytest.raises(TokenInvalid):
        verifier.verify(make_token(kid="kid-desconocido"))


def test_jwks_unreachable_is_503(monkeypatch, build_app, make_token) -> None:
    def fail(self: Any) -> Any:
        raise jwt.PyJWKClientConnectionError("sin red")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fail)
    verifier = CognitoTokenVerifier(ISSUER, CLIENT_ID, jwks_key_resolver(f"{ISSUER}/.well-known/jwks.json"))
    with pytest.raises(KeySourceUnavailable):
        verifier.verify(make_token())
    with running(build_app(verifier=verifier)) as test_client:
        response = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
