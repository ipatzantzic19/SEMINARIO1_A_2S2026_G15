"""scripts/face_smoke.py: lógica pura y ejecución completa contra la APP REAL de Python.

La app corre con TestClient, un Cognito de doble que decide por la clave de la captura, S3 y upload falsos y un
reloj falso para el vencimiento. Cognito, la Lambda, el trigger y Rekognition reales solo se ejercitan al
ejecutar el script en la EC2 (docs/api/python-face-login.md §7).
"""

from __future__ import annotations

import importlib.util
import io
import itertools
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from app.common.errors import ApiError
from app.modules.auth.face import FaceLoginService
from app.modules.auth.face_store import FaceChallengeStore
from app.modules.integrations.cognito.gateway import AuthChallenge
from tests.conftest import COMPLETE_SUB, running
from tests.fakes import FakeCognito, tokens

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    spec = importlib.util.spec_from_file_location("face_smoke", SCRIPTS / "face_smoke.py")
    smoke = importlib.util.module_from_spec(spec)
    sys.modules["face_smoke"] = smoke
    spec.loader.exec_module(smoke)
finally:
    sys.path.remove(str(SCRIPTS))

import face_probe as probe  # noqa: E402  (cargado por face_smoke; es el mismo módulo)

EMAIL = "ana.secreta@example.com"
UNKNOWN = "no.existe.abc@example.invalid"
PASSWORD = "clave-de-ana-1234!"
OWN_KEY = "Fotos_Perfil/references/sub-propio/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.jpg"
OTHER_KEY = "Fotos_Perfil/references/sub-ajeno/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb.jpg"
JPEG_OWN = b"\xff\xd8\xff\xe0" + b"propio" * 10
JPEG_OTHER = b"\xff\xd8\xff\xe0" + b"ajeno" * 10
NOW = datetime(2026, 10, 26, 18, 0, 0, tzinfo=timezone.utc)
API = "http://testserver/api/v1"
INTERNAL_SESSION = "SESSION-INTERNA-" + "z" * 40


class Clock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value


class ScriptedCognito(FakeCognito):
    """InitiateAuth crea un reto por llamada; RespondToAuthChallenge acepta solo la captura marcada 'propio'."""

    def __init__(self, make_token: Any, *, accept_everything: bool = False) -> None:
        super().__init__()
        self._make_token = make_token
        self._count = itertools.count(1)
        self.accept_everything = accept_everything
        self.responds = 0

    def initiate_custom_auth(self, email: str) -> Any:
        self._record("initiate_custom_auth", email=email)
        if email.startswith("no.existe."):
            raise ApiError(401, "UNAUTHENTICATED", None, {"reason": "FACE_UNKNOWN_USER"})
        challenge_id = f"00000000-0000-4000-8000-{next(self._count):012d}"
        return AuthChallenge(
            "CUSTOM_CHALLENGE", INTERNAL_SESSION,
            {"challengeId": challenge_id, "purpose": "faceCapture", "expiresInSeconds": "120", "USERNAME": COMPLETE_SUB},
        )

    def respond_to_custom_challenge(self, *, username: str, session: str, answer: str) -> Any:
        self._record("respond_to_custom_challenge", username=username, session=session, answer=answer)
        self.responds += 1
        if self.accept_everything or json.loads(answer)["captureKey"].endswith("/propio"):
            return tokens(self._make_token(COMPLETE_SUB))
        raise ApiError(422, "FACE_NOT_MATCHED")


class FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}


class _ClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__("mensaje interno de AWS")
        self.response = {"Error": {"Code": code, "Message": "mensaje interno de AWS"}}


def make_upload_factory(seen_tokens: list[str], *, status: int = 201):
    marks = {JPEG_OWN: "propio", JPEG_OTHER: "ajeno"}

    def factory(token: str):
        def upload(challenge_id: str, image: bytes, content_type: str) -> Any:
            seen_tokens.append(token)
            key = f"Fotos_Perfil/captures/{challenge_id}/{marks[image]}"
            return probe.Uploaded(status, key if status == 201 else None, 9.0)

        return upload

    return factory


@pytest.fixture
def env(build_app, make_token):
    cognito = ScriptedCognito(make_token)
    clock = Clock()
    app = build_app(cognito_gateway=cognito)
    app.state.face_service = FaceLoginService(
        cognito, app.state.auth_service, FaceChallengeStore(clock=clock), "Fotos_Perfil/captures/",
        wall_clock=lambda: NOW,
    )
    with running(app) as client:

        def http(method: str, url: str, token: str | None = None, json_body: Any = None) -> Any:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            started = time.perf_counter()
            response = client.request(method, url.removeprefix("http://testserver"), json=json_body, headers=headers)
            body = response.json() if response.content else None
            return smoke.Resp(response.status_code, body, (time.perf_counter() - started) * 1000)

        yield type("Env", (), {"cognito": cognito, "clock": clock, "http": http, "client": client, "app": app})


def build(env, *, upload_status: int = 201, objects: dict[str, bytes] | None = None):
    seen: list[str] = []
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        env.clock.value += seconds

    runner = smoke.Smoke(
        env.http,
        FakeS3(objects if objects is not None else {OWN_KEY: JPEG_OWN, OTHER_KEY: JPEG_OTHER}),
        make_upload_factory(seen, status=upload_status),
        api=API,
        bucket="bucket-test",
        sleep=sleep,
        clock=lambda: NOW,
    )
    return runner, seen, slept


def run(runner, **kwargs: Any) -> int:
    defaults = dict(email=EMAIL, reference_key=OWN_KEY, other_reference_key=OTHER_KEY, unknown_email=UNKNOWN,
                    skip_expiry=False)
    return runner.run(**{**defaults, **kwargs})


# --- lógica pura --------------------------------------------------------------------------------------


def test_challenge_shape_problem() -> None:
    good = {"challengeId": "00000000-0000-4000-8000-000000000001", "expiresAt": "2026-10-26T18:02:00.000Z",
            "uploadToken": "abc"}
    assert smoke.challenge_shape_problem(good) is None
    assert smoke.challenge_shape_problem({**good, "extra": 1}) is not None
    assert smoke.challenge_shape_problem({**good, "challengeId": "no-uuid"}) is not None
    assert smoke.challenge_shape_problem({**good, "expiresAt": "ayer"}) is not None
    assert smoke.challenge_shape_problem({**good, "uploadToken": ""}) is not None
    assert smoke.challenge_shape_problem(None) is not None


def test_token_set_problem() -> None:
    good = {"accessToken": "a", "idToken": "i", "refreshToken": "r", "expiresIn": 3600, "tokenType": "Bearer",
            "profileComplete": True}
    assert smoke.token_set_problem(good) is None
    assert smoke.token_set_problem({**good, "tokenType": "bearer"}) is not None
    assert smoke.token_set_problem({**good, "profileComplete": "yes"}) is not None
    assert smoke.token_set_problem({k: good[k] for k in reversed(list(good))}) is not None  # orden del contrato
    assert smoke.token_set_problem({**good, "idToken": ""}) is not None


def test_seconds_until_and_shape() -> None:
    assert smoke.seconds_until("2026-10-26T18:02:00.000Z", NOW) == 120.0
    assert smoke.seconds_until("2026-10-26T17:59:00.000Z", NOW) == -60.0
    assert smoke.shape({"a": 1, "b": "x"}) == [("a", "int"), ("b", "str")]


# --- ejecución completa contra la app real ------------------------------------------------------------


def test_full_run_against_real_app_is_ok_and_leaks_nothing(env, make_token, capsys) -> None:
    runner, seen, slept = build(env)
    code = run(runner)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "FALLO" not in out and "RESULTADO: OK" in out
    for fragment in ("1)", "2a)", "2b)", "3)", "3b)", "4)", "5)", "5b)", "6)", "6b)", "7)"):
        assert any(line.startswith("OK") and f" {fragment}" in line for line in out.splitlines()), fragment
    assert slept == [pytest.approx(123.0)]  # 120 s de vigencia + 3 s de margen
    # El uploadToken que entrega la API es el que se usa en la subida (distinto por reto).
    assert len(set(seen)) == len(seen) and all(len(t) >= 40 for t in seen)
    assert env.cognito.responds == 2  # positivo + ajena; los inválidos, el reuso y el falso no llegan a Cognito
    for secret in (EMAIL, UNKNOWN, INTERNAL_SESSION, COMPLETE_SUB, "sub-propio", "sub-ajeno", "aaaaaaaa", *seen):
        assert secret not in out


def test_skip_expiry_omits_the_wait(env, capsys) -> None:
    runner, _, slept = build(env)
    assert run(runner, skip_expiry=True) == 0
    assert slept == [] and "OMITIDO 7)" in capsys.readouterr().out


def test_compare_login_checks_same_token_set_shape(env, make_token, capsys) -> None:
    env.cognito.auth_results = [tokens(make_token(COMPLETE_SUB))]
    runner, _, _ = build(env)
    assert run(runner, skip_expiry=True, login_password=PASSWORD) == 0
    out = capsys.readouterr().out
    assert "OK    3c) misma forma de TokenSet que /auth/login" in out and PASSWORD not in out


def test_foreign_image_accepted_by_cognito_is_reported_as_failure(env, make_token, capsys) -> None:
    env.cognito.accept_everything = True
    runner, _, _ = build(env)
    assert run(runner, skip_expiry=True) == 1
    assert "FALLO 5) verify con imagen ajena → 422" in capsys.readouterr().out


def test_upload_failure_stops_the_run(env, capsys) -> None:
    runner, _, _ = build(env, upload_status=415)
    assert run(runner) == 1
    out = capsys.readouterr().out
    assert "FALLO 3) captura propia: subida faceCapture" in out and "Se detiene" in out


def test_missing_reference_is_reported_without_the_key(env, capsys) -> None:
    runner, _, _ = build(env, objects={})
    assert run(runner) == 1
    out = capsys.readouterr().out
    assert "NoSuchKey" in out and OWN_KEY not in out and "mensaje interno" not in out


def test_api_down_is_reported_as_failure(capsys) -> None:
    def down(*_: Any, **__: Any) -> Any:
        return smoke.Resp(0, None, 1.0)

    runner = smoke.Smoke(down, FakeS3({}), make_upload_factory([]), api=API, bucket="b")
    assert runner.run(email=EMAIL, reference_key=OWN_KEY, other_reference_key=OTHER_KEY, unknown_email=UNKNOWN,
                      skip_expiry=True) == 1
    assert "FALLO 1) POST /auth/face/challenges" in capsys.readouterr().out


def test_main_rejects_bad_arguments(capsys) -> None:
    base = ["--email", EMAIL]
    assert smoke.main(base + ["--reference-key", "Fotos_Perfil/public/x/y.jpg", "--other-reference-key", OTHER_KEY]) == 2
    assert smoke.main(base + ["--reference-key", OWN_KEY, "--other-reference-key", OWN_KEY]) == 2
    assert smoke.main(base + ["--reference-key", OWN_KEY, "--other-reference-key", OTHER_KEY,
                              "--upload-url", "http://inseguro.test"]) == 2
    assert EMAIL not in capsys.readouterr().err
