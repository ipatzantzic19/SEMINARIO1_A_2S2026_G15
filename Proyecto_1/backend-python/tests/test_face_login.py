"""Login facial: POST /auth/face/challenges y /auth/face/challenges/{id}/verify con dobles (PRO-14).

Cognito se reemplaza por ``FakeCognito`` (el mapeo de cada error de AWS ya se prueba con Stubber en
test_cognito_face.py) y el almacén usa un reloj falso. Nada de esto prueba Cognito, S3 ni Rekognition reales:
eso queda para scripts/face_probe.py y scripts/face_smoke.py en la EC2 (docs/api/python-face-login.md §7).
"""

from __future__ import annotations

import itertools
import json
import threading
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
import jwt

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.auth.face import FaceLoginService
from app.modules.auth.face_store import FaceChallenge, FaceChallengeStore
from app.modules.integrations.cognito.gateway import AuthChallenge
from tests.conftest import COMPLETE_SUB, INCOMPLETE_SUB, UNKNOWN_SUB, assert_error, running, seeded_users, local_settings
from tests.fakes import FakeCognito, challenge, tokens
from tests.test_contract import validate

CREATE = "/api/v1/auth/face/challenges"
CID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_CID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
PREFIX = "Fotos_Perfil/captures/"
CAPTURE = f"{PREFIX}{CID}/cccccccc-cccc-4ccc-8ccc-cccccccccccc.jpg"
SESSION = "SESSION-" + "x" * 50
INTERNAL_USERNAME = "11111111-1111-4111-8111-111111111111"
EMAIL = "Ana.Secreta@Example.com"
NOW = datetime(2026, 10, 26, 18, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, value: float = 1000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def verify_url(challenge_id: str = CID) -> str:
    return f"{CREATE}/{challenge_id}/verify"


def cognito_challenge(challenge_id: str = CID, *, session: str = SESSION, **params: str) -> AuthChallenge:
    parameters = {"challengeId": challenge_id, "purpose": "faceCapture", "expiresInSeconds": "120",
                  "USERNAME": INTERNAL_USERNAME, **params}
    return AuthChallenge("CUSTOM_CHALLENGE", session, parameters)


@pytest.fixture
def world(build_app):
    cognito = FakeCognito()
    users = seeded_users()
    clock = Clock()
    store = FaceChallengeStore(clock=clock, max_entries=5)
    app = build_app(cognito_gateway=cognito, users_repository=users)
    counter = itertools.count(1)
    app.state.face_service = FaceLoginService(
        cognito,
        app.state.auth_service,
        store,
        PREFIX,
        wall_clock=lambda: NOW,
        token_factory=lambda *_: f"upload-token-{next(counter)}",
        id_factory=lambda: f"dec0{next(counter):04d}-0000-4000-8000-000000000000",
    )
    with running(app) as client:
        yield SimpleNamespace(client=client, cognito=cognito, users=users, clock=clock, store=store)


def start(world: Any, challenge_id: str = CID, **kwargs: Any) -> dict[str, Any]:
    world.cognito.face_init_results = [cognito_challenge(challenge_id, **kwargs)]
    response = world.client.post(CREATE, json={"email": EMAIL})
    assert response.status_code == 201, response.text
    return response.json()


def responded(world: Any) -> list[dict[str, Any]]:
    return [kw for name, kw in world.cognito.calls if name == "respond_to_custom_challenge"]


# --- POST /auth/face/challenges -----------------------------------------------


def test_create_challenge_returns_contract_shape_and_stores_session(world) -> None:
    body = start(world)
    assert set(body) == {"challengeId", "expiresAt", "uploadToken"}
    assert body["challengeId"] == CID  # lo emite el trigger CreateAuthChallenge, no Python
    assert body["expiresAt"] == "2026-10-26T18:02:00.000Z"  # +120 s
    assert body["uploadToken"] == "upload-token-1"
    # Cognito recibe el correo normalizado; nada más (sin SecretHash ni contraseña).
    assert world.cognito.calls == [("initiate_custom_auth", {"email": "ana.secreta@example.com"})]
    assert len(world.store) == 1


def test_default_upload_token_is_signed_and_bound_to_challenge(build_app, face_signing_file, public_pem) -> None:
    cognito = FakeCognito()
    settings = replace(local_settings(), face_upload_private_key_file=face_signing_file, face_upload_key_id="face-v1")
    app = build_app(cognito_gateway=cognito, settings=settings)
    cognito.face_init_results = [cognito_challenge(CID), cognito_challenge(OTHER_CID)]
    with running(app) as client:
        first = client.post(CREATE, json={"email": "a@example.com"}).json()["uploadToken"]
        second = client.post(CREATE, json={"email": "a@example.com"}).json()["uploadToken"]
    assert first != second
    for token, cid in ((first, CID), (second, OTHER_CID)):
        claims = jwt.decode(token, public_pem, algorithms=["RS256"], audience="semisocial-image-upload",
                            issuer="semisocial-face-auth")
        assert claims["challengeId"] == cid and claims["purpose"] == "faceCapture"


@pytest.mark.parametrize(("value", "expected"), [("5", 30), ("9999", 300), ("abc", 120), ("45", 45)])
def test_ttl_comes_from_cognito_parameters_with_limits(world, value: str, expected: int) -> None:
    start(world, expiresInSeconds=value)
    assert world.clock.value + expected == world.store._items[CID].expires_at  # noqa: SLF001


def test_username_falls_back_to_email_when_cognito_omits_it(world) -> None:
    world.cognito.face_init_results = [AuthChallenge("CUSTOM_CHALLENGE", SESSION, {"challengeId": CID})]
    assert world.client.post(CREATE, json={"email": EMAIL}).status_code == 201
    world.cognito.face_respond_results = [tokens("x")]
    world.client.post(verify_url(), json={"captureKey": CAPTURE})
    assert responded(world)[0]["username"] == "ana.secreta@example.com"


def test_unknown_user_gets_identical_201_and_fails_later_with_422(world) -> None:
    real = start(world)
    world.cognito.face_init_results = [ApiError(401, "UNAUTHENTICATED", None, {"reason": "FACE_UNKNOWN_USER"})]
    decoy_response = world.client.post(CREATE, json={"email": "nadie@example.com"})
    assert decoy_response.status_code == 201
    decoy = decoy_response.json()
    assert set(decoy) == set(real) and decoy["challengeId"] != real["challengeId"]
    assert decoy["expiresAt"] == real["expiresAt"]

    calls_before = len(world.cognito.calls)
    key = f"{PREFIX}{decoy['challengeId']}/x.jpg"
    assert_error(world.client.post(verify_url(decoy["challengeId"]), json={"captureKey": key}), 422, "FACE_NOT_MATCHED")
    assert len(world.cognito.calls) == calls_before  # el reto falso nunca llega a Cognito
    assert_error(world.client.post(verify_url(decoy["challengeId"]), json={"captureKey": key}), 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "outcome",
    [
        tokens("no-deberia-ocurrir"),
        AuthChallenge("NEW_PASSWORD_REQUIRED", SESSION, {"challengeId": CID}),
        AuthChallenge("CUSTOM_CHALLENGE", SESSION, {"purpose": "faceCapture"}),
    ],
    ids=["tokens", "otro-reto", "sin-challengeId"],
)
def test_unexpected_cognito_outcome_returns_decoy_201(world, outcome) -> None:
    world.cognito.face_init_results = [outcome]
    response = world.client.post(CREATE, json={"email": EMAIL})
    assert response.status_code == 201
    assert response.json()["challengeId"].startswith("dec0")
    assert SESSION not in response.text and "no-deberia-ocurrir" not in response.text


@pytest.mark.parametrize(
    ("error", "status", "code", "reason"),
    [
        (ApiError(400, "VALIDATION_ERROR", "x", {"reason": "FACE_REFERENCE_MISSING"}), 400, "VALIDATION_ERROR", "FACE_REFERENCE_MISSING"),
        (ApiError(401, "UNAUTHENTICATED", "x", {"reason": "USER_NOT_CONFIRMED"}), 401, "UNAUTHENTICATED", "USER_NOT_CONFIRMED"),
        (ApiError(401, "UNAUTHENTICATED", "x", {"reason": "PASSWORD_RESET_REQUIRED"}), 401, "UNAUTHENTICATED", "PASSWORD_RESET_REQUIRED"),
        (ApiError(429, "RATE_LIMITED"), 429, "RATE_LIMITED", None),
        (ServiceUnavailableError(), 503, "SERVICE_UNAVAILABLE", None),
    ],
    ids=["sin-referencia", "sin-confirmar", "restablecer", "limite", "no-disponible"],
)
def test_create_challenge_errors(world, error, status, code, reason) -> None:
    world.cognito.face_init_results = [error]
    body = assert_error(world.client.post(CREATE, json={"email": EMAIL}), status, code)
    assert (body["details"] or {}).get("reason") == reason
    assert len(world.store) == 0


@pytest.mark.parametrize("payload", [{}, {"email": "no-es-correo"}, {"email": "a@b.c\n"}, {"email": 3}])
def test_create_challenge_validates_body_before_cognito(world, payload) -> None:
    assert_error(world.client.post(CREATE, json=payload), 400, "VALIDATION_ERROR")
    assert world.cognito.calls == []


def test_store_cap_answers_429_without_evicting(world) -> None:
    for i in range(5):
        start(world, f"{i:08d}-0000-4000-8000-000000000000")
    world.cognito.face_init_results = [cognito_challenge(CID)]
    assert_error(world.client.post(CREATE, json={"email": EMAIL}), 429, "RATE_LIMITED")
    assert len(world.store) == 5
    world.clock.value += 121  # los caducados se limpian y vuelve a haber espacio
    assert start(world)["challengeId"] == CID


# --- POST /auth/face/challenges/{id}/verify --------------------------------------


@pytest.mark.parametrize(("sub", "complete"), [(COMPLETE_SUB, True), (INCOMPLETE_SUB, False)])
def test_verify_returns_cognito_token_set_like_login(world, make_token, sub: str, complete: bool) -> None:
    start(world)
    access = make_token(sub)
    world.cognito.face_respond_results = [tokens(access)]
    response = world.client.post(verify_url(), json={"captureKey": CAPTURE})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "accessToken": access,
        "idToken": "id-token",
        "refreshToken": "refresh-token",
        "expiresIn": 3600,
        "tokenType": "Bearer",
        "profileComplete": complete,
    }
    # RespondToAuthChallenge: Session y USERNAME del reto y el ANSWER exacto que espera el trigger.
    [call] = responded(world)
    assert call["username"] == INTERNAL_USERNAME and call["session"] == SESSION
    assert json.loads(call["answer"]) == {"challengeId": CID, "purpose": "faceCapture", "captureKey": CAPTURE}
    assert list(json.loads(call["answer"])) == ["challengeId", "purpose", "captureKey"]


def test_verify_consumes_the_challenge_once(world, make_token) -> None:
    start(world)
    world.cognito.face_respond_results = [tokens(make_token(COMPLETE_SUB))]
    assert world.client.post(verify_url(), json={"captureKey": CAPTURE}).status_code == 200
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")
    assert len(responded(world)) == 1


def test_verify_reconciles_missing_row_like_login(world, make_token) -> None:
    start(world)
    world.cognito.face_respond_results = [tokens(make_token(UNKNOWN_SUB))]
    world.cognito.user_attributes = {"sub": UNKNOWN_SUB, "email": "nuevo@example.com", "name": "Nuevo Usuario",
                                     "custom:dpi": "4444444444444"}
    response = world.client.post(verify_url(), json={"captureKey": CAPTURE})
    assert response.status_code == 200, response.text
    assert response.json()["profileComplete"] is False
    assert UNKNOWN_SUB in world.users.rows


def test_verify_rejects_token_that_does_not_verify(world, make_token) -> None:
    start(world)
    world.cognito.face_respond_results = [tokens(make_token(COMPLETE_SUB, client_id="otro-cliente"))]
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 503, "SERVICE_UNAVAILABLE")
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")


def test_no_match_with_attempts_left_is_422_and_discards_challenge(world) -> None:
    start(world)
    world.cognito.face_respond_results = [cognito_challenge(OTHER_CID, session="NUEVA-" + "n" * 50)]
    response = world.client.post(verify_url(), json={"captureKey": CAPTURE})
    body = assert_error(response, 422, "FACE_NOT_MATCHED")
    assert body["message"] == "No fue posible verificar el rostro."
    assert "NUEVA-" not in response.text and OTHER_CID not in response.text  # el reto nuevo no se filtra
    assert len(world.store) == 0
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")
    assert_error(world.client.post(verify_url(OTHER_CID), json={"captureKey": f"{PREFIX}{OTHER_CID}/x.jpg"}), 404, "NOT_FOUND")


def test_not_authorized_from_cognito_is_422_and_discards_challenge(world) -> None:
    start(world)
    world.cognito.face_respond_results = [ApiError(422, "FACE_NOT_MATCHED")]
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 422, "FACE_NOT_MATCHED")
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")


def test_throttling_keeps_the_challenge(world, make_token) -> None:
    start(world)
    world.cognito.face_respond_results = [ApiError(429, "RATE_LIMITED"), tokens(make_token(COMPLETE_SUB))]
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 429, "RATE_LIMITED")
    assert len(world.store) == 1
    assert world.client.post(verify_url(), json={"captureKey": CAPTURE}).status_code == 200


def test_cognito_failure_is_503_and_discards_challenge(world) -> None:
    start(world)
    world.cognito.face_respond_results = [ServiceUnavailableError()]
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 503, "SERVICE_UNAVAILABLE")
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")


def test_unknown_challenge_is_404_without_calling_cognito(world) -> None:
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")
    assert world.cognito.calls == []


def test_expired_challenge_is_404_without_calling_cognito(world) -> None:
    start(world)
    world.clock.value += 121
    assert_error(world.client.post(verify_url(), json={"captureKey": CAPTURE}), 404, "NOT_FOUND")
    assert responded(world) == []


@pytest.mark.parametrize(
    "capture_key",
    [
        f"{PREFIX}{CID}/../{OTHER_CID}/x.jpg",
        f"{PREFIX}{CID}/..",
        f"{PREFIX}{OTHER_CID}/x.jpg",
        f"Fotos_Perfil/references/{INTERNAL_USERNAME}/x.jpg",
        f"Fotos_Perfil/public/{INTERNAL_USERNAME}/x.jpg",
        f"{PREFIX}{CID}/",
        f"{PREFIX}{CID}",
        f"{PREFIX}{CID}/sub/x.jpg",
        f"{PREFIX}{CID}/x y.jpg",
        f"https://evil.example/{PREFIX}{CID}/x.jpg",
        f"/{PREFIX}{CID}/x.jpg",
        "x.jpg",
    ],
)
def test_invalid_capture_key_is_400_and_does_not_consume_challenge(world, make_token, capture_key: str) -> None:
    start(world)
    body = assert_error(world.client.post(verify_url(), json={"captureKey": capture_key}), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_CAPTURE_KEY"}
    assert responded(world) == [] and len(world.store) == 1
    world.cognito.face_respond_results = [tokens(make_token(COMPLETE_SUB))]
    assert world.client.post(verify_url(), json={"captureKey": CAPTURE}).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [{}, {"captureKey": ""}, {"captureKey": 3}, {"captureKey": "x" * 1025}, {"captureKey": f"{PREFIX}{CID}/" + "a" * 1100}],
)
def test_verify_validates_body(world, payload) -> None:
    start(world)
    assert_error(world.client.post(verify_url(), json=payload), 400, "VALIDATION_ERROR")
    assert len(world.store) == 1


def test_verify_rejects_non_uuid_challenge_id(world) -> None:
    assert_error(world.client.post(verify_url("no-es-uuid"), json={"captureKey": CAPTURE}), 400, "VALIDATION_ERROR")


# --- logs: ninguna pieza sensible ---------------------------------------------------


def test_logs_never_contain_email_session_tokens_keys_or_answer(world, make_token, log_stream) -> None:
    start(world)
    access = make_token(COMPLETE_SUB)
    world.cognito.face_respond_results = [tokens(access)]
    ok = world.client.post(verify_url(), json={"captureKey": CAPTURE})
    start(world, OTHER_CID)
    world.cognito.face_respond_results = [cognito_challenge(CID)]
    world.client.post(verify_url(OTHER_CID), json={"captureKey": f"{PREFIX}{OTHER_CID}/x.jpg"})
    world.client.post(verify_url(), json={"captureKey": "mal"})
    logs = log_stream.getvalue()
    for event in ("face.challenge_created", "face.verified", "face.not_matched"):
        assert event in logs
    for secret in (EMAIL, EMAIL.lower(), SESSION, access, ok.json()["refreshToken"], "upload-token-", CAPTURE,
                   "captureKey", "challengeAnswer", INTERNAL_USERNAME, "cccccccc"):
        assert secret not in logs, secret


# --- contrato (openapi.yaml) --------------------------------------------------------


def test_responses_match_openapi(world, make_token) -> None:
    def post(url: str, body: dict[str, Any]) -> Any:
        response = world.client.post(url, json=body)
        validate(response, "post", url, json.dumps(body).encode())
        return response

    world.cognito.face_init_results = [cognito_challenge()]
    assert post(CREATE, {"email": EMAIL}).status_code == 201
    assert post(CREATE, {}).status_code == 400
    world.cognito.face_init_results = [ApiError(429, "RATE_LIMITED")]
    assert post(CREATE, {"email": EMAIL}).status_code == 429

    world.cognito.face_respond_results = [tokens(make_token(COMPLETE_SUB))]
    assert post(verify_url(), {"captureKey": CAPTURE}).status_code == 200
    assert post(verify_url(), {"captureKey": CAPTURE}).status_code == 404
    assert post(verify_url(), {"captureKey": "mal"}).status_code == 400
    start(world)
    world.cognito.face_respond_results = [ApiError(422, "FACE_NOT_MATCHED")]
    assert post(verify_url(), {"captureKey": CAPTURE}).status_code == 422


# --- almacén ---------------------------------------------------------------------------


def make_challenge(cid: str, expires_at: float) -> FaceChallenge:
    return FaceChallenge(cid, "usuario", "session", "token", expires_at)


def test_store_take_is_atomic_across_threads() -> None:
    store = FaceChallengeStore(clock=Clock())
    store.add(make_challenge("c1", 2000.0))
    winners: list[FaceChallenge] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        found = store.take("c1")
        if found is not None:
            winners.append(found)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(winners) == 1 and len(store) == 0


def test_store_expiry_cleanup_and_put_back() -> None:
    clock = Clock()
    store = FaceChallengeStore(max_entries=2, clock=clock)
    store.add(make_challenge("a", 1010.0))
    store.add(make_challenge("b", 1100.0))
    clock.value = 1020.0
    assert len(store) == 1  # "a" venció y se limpió
    taken = store.take("b")
    assert taken is not None and len(store) == 0
    store.put_back(taken)
    assert len(store) == 1
    clock.value = 1200.0
    store.put_back(taken)  # vencido: no se devuelve
    assert len(store) == 0 and store.take("b") is None


def test_store_repr_hides_secrets() -> None:
    text = repr(FaceChallenge("c1", "correo@secreto.com", "SESION-SECRETA", "TOKEN-SECRETO", 1.0))
    assert "c1" in text
    for secret in ("correo@secreto.com", "SESION-SECRETA", "TOKEN-SECRETO"):
        assert secret not in text


def test_store_rejects_non_positive_capacity() -> None:
    with pytest.raises(ValueError):
        FaceChallengeStore(max_entries=0)
