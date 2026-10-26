"""scripts/face_probe.py (puerta 0 del login facial): lógica pura y ejecución con dobles de Cognito, S3 y upload.

Nada de AWS real: eso solo se ejercita al ejecutar el script en la EC2 (docs/api/python-face-login.md §7).
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from email.parser import BytesParser
from email.policy import HTTP
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("face_probe", SCRIPTS / "face_probe.py")
probe = importlib.util.module_from_spec(spec)
sys.modules["face_probe"] = probe
spec.loader.exec_module(probe)

EMAIL = "ana.secreta@example.com"
CLIENT_ID = "client-test"
BUCKET = "bucket-test"
OWN_KEY = "Fotos_Perfil/references/sub-propio/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.jpg"
OTHER_KEY = "Fotos_Perfil/references/sub-ajeno/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb.jpg"
JPEG_OWN = b"\xff\xd8\xff\xe0" + b"propio" * 10
JPEG_OTHER = b"\xff\xd8\xff\xe0" + b"ajeno" * 10
SESSION_SECRET = "session-ultra-secreta"
TOKEN_SECRET = "token-ultra-secreto"


class ClientError(Exception):
    def __init__(self, code: str, message: str = "mensaje interno de AWS") -> None:
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}}


class FakeCognito:
    """Reto nuevo por InitiateAuth; Cognito solo entrega tokens si la captura es la de la referencia propia."""

    def __init__(self, *, init_error: ClientError | None = None) -> None:
        self.init_error = init_error
        self.count = 0
        self.consumed: set[str] = set()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def initiate_auth(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("initiate_auth", kwargs))
        if self.init_error:
            raise self.init_error
        self.count += 1
        challenge_id = f"00000000-0000-4000-8000-{self.count:012d}"
        return {
            "ChallengeName": "CUSTOM_CHALLENGE",
            "Session": f"{SESSION_SECRET}-{challenge_id}",
            "ChallengeParameters": {"challengeId": challenge_id, "purpose": "faceCapture",
                                    "expiresInSeconds": "120", "USERNAME": "sub-interno"},
        }

    def respond_to_auth_challenge(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("respond_to_auth_challenge", kwargs))
        session = kwargs["Session"]
        if session in self.consumed:
            raise ClientError("NotAuthorizedException")
        answer = json.loads(kwargs["ChallengeResponses"]["ANSWER"])
        self.consumed.add(session)
        if answer["captureKey"].endswith("/propio"):
            return {"AuthenticationResult": {"AccessToken": TOKEN_SECRET}}
        raise ClientError("NotAuthorizedException")


class FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.requests: list[str] = []

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self.requests.append(Key)
        if Key not in self.objects:
            raise ClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}


def make_upload(*, status: int = 201, mark: dict[bytes, str] | None = None) -> Any:
    marks = mark or {JPEG_OWN: "propio", JPEG_OTHER: "ajeno"}
    uploads: list[tuple[str, bytes]] = []

    def upload(challenge_id: str, image: bytes, content_type: str) -> Any:
        uploads.append((challenge_id, image))
        key = f"Fotos_Perfil/captures/{challenge_id}/{marks[image]}"
        return probe.Uploaded(status, key if status == 201 else None, 12.0)

    upload.calls = uploads  # type: ignore[attr-defined]
    return upload


def run_probe(cognito: FakeCognito, s3: FakeS3, upload: Any) -> int:
    return probe.run(cognito, s3, upload, client_id=CLIENT_ID, bucket=BUCKET, email=EMAIL,
                     reference_key=OWN_KEY, other_reference_key=OTHER_KEY)


# --- lógica pura -------------------------------------------------------------------------------------


def test_multipart_has_fields_and_file() -> None:
    body, header = probe.build_multipart(
        {"purpose": "faceCapture", "challengeId": "abc"}, "file", "captura", "image/jpeg", JPEG_OWN, boundary="B"
    )
    assert header == "multipart/form-data; boundary=B"
    message = BytesParser(policy=HTTP).parsebytes(b"Content-Type: " + header.encode() + b"\r\n\r\n" + body)
    parts = {p.get_param("name", header="content-disposition"): p.get_payload(decode=True) for p in message.iter_parts()}
    assert parts["purpose"] == b"faceCapture" and parts["challengeId"] == b"abc" and parts["file"] == JPEG_OWN


def test_answer_matches_trigger_contract() -> None:
    answer = json.loads(probe.answer_json("cid", "Fotos_Perfil/captures/cid/x.jpg"))
    assert answer == {"challengeId": "cid", "purpose": "faceCapture", "captureKey": "Fotos_Perfil/captures/cid/x.jpg"}


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xff\xd8\xff\xe0abc", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nxxxx", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPxxxx", "image/webp"),
        (b"texto plano", None),
    ],
)
def test_image_content_type(data: bytes, expected: str | None) -> None:
    assert probe.image_content_type(data) == expected


def test_capture_key_validation() -> None:
    assert probe.capture_key_is_valid("cid", "Fotos_Perfil/captures/cid/a.jpg")
    assert not probe.capture_key_is_valid("cid", "Fotos_Perfil/captures/otro/a.jpg")
    assert not probe.capture_key_is_valid("cid", "Fotos_Perfil/captures/cid/../a.jpg")
    assert not probe.capture_key_is_valid("cid", None)


def test_aws_code_never_returns_message() -> None:
    assert probe.aws_code(ClientError("NotAuthorizedException", "secreto")) == "NotAuthorizedException"
    assert probe.aws_code(ValueError("secreto")) == "ValueError"
    assert probe.is_missing_reference(ClientError("UserLambdaValidationException", "x failed with error MISSING_FACE_REFERENCE."))
    assert not probe.is_missing_reference(ClientError("UserLambdaValidationException", "otro"))


def test_keys_are_valid() -> None:
    assert probe.keys_are_valid(OWN_KEY, OTHER_KEY)
    assert not probe.keys_are_valid("Fotos_Perfil/public/x/y.jpg")
    assert not probe.keys_are_valid("Fotos_Perfil/references/../public/x.jpg")
    assert not probe.keys_are_valid("Fotos_Perfil/references/sub/")


# --- ejecución completa con dobles -----------------------------------------------------------------


def test_full_run_ok_without_leaking_secrets(capsys) -> None:
    cognito = FakeCognito()
    code = run_probe(cognito, FakeS3({OWN_KEY: JPEG_OWN, OTHER_KEY: JPEG_OTHER}), make_upload())
    out = capsys.readouterr().out
    assert code == 0, out
    assert "FALLO" not in out and "RESULTADO: OK" in out
    lines = [line for line in out.splitlines() if line.startswith("OK")]
    for step in ("a)", "b)", "c)", "d)", "e)"):
        assert any(f" {step} " in line for line in lines), step
    assert all(secret not in out for secret in (EMAIL, SESSION_SECRET, TOKEN_SECRET, "sub-propio", "sub-ajeno", "aaaaaaaa", "sub-interno"))
    # RespondToAuthChallenge usa el USERNAME interno devuelto por Cognito.
    respond_calls = [kw for name, kw in cognito.calls if name == "respond_to_auth_challenge"]
    assert {kw["ChallengeResponses"]["USERNAME"] for kw in respond_calls} == {"sub-interno"}
    assert all(kw["ChallengeName"] == "CUSTOM_CHALLENGE" for kw in respond_calls)


def test_initiate_failure_stops_and_names_only_the_code(capsys) -> None:
    cognito = FakeCognito(init_error=ClientError("UserLambdaValidationException", "x failed with error MISSING_FACE_REFERENCE."))
    code = run_probe(cognito, FakeS3({}), make_upload())
    out = capsys.readouterr().out
    assert code == 1
    assert "UserLambdaValidationException" in out and "custom:face_reference_key" in out
    assert "failed with error" not in out


def test_upload_failure_is_reported(capsys) -> None:
    code = run_probe(FakeCognito(), FakeS3({OWN_KEY: JPEG_OWN, OTHER_KEY: JPEG_OTHER}), make_upload(status=415))
    out = capsys.readouterr().out
    assert code == 1 and "FALLO b) captura propia: subida faceCapture" in out


def test_missing_reference_object_is_reported(capsys) -> None:
    code = run_probe(FakeCognito(), FakeS3({}), make_upload())
    out = capsys.readouterr().out
    assert code == 1 and "NoSuchKey" in out and OWN_KEY not in out


def test_tokens_for_foreign_image_are_a_failure(capsys) -> None:
    class Lenient(FakeCognito):
        def respond_to_auth_challenge(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(("respond_to_auth_challenge", kwargs))
            return {"AuthenticationResult": {"AccessToken": TOKEN_SECRET}}

    code = run_probe(Lenient(), FakeS3({OWN_KEY: JPEG_OWN, OTHER_KEY: JPEG_OTHER}), make_upload())
    out = capsys.readouterr().out
    assert code == 1
    assert "SE EMITIERON TOKENS con una imagen ajena" in out
    assert "SE EMITIERON TOKENS con un reto ya consumido" in out
    assert TOKEN_SECRET not in out


def test_main_rejects_bad_arguments(capsys) -> None:
    base = ["--email", EMAIL, "--upload-url", "https://u.test/uploads/images"]
    assert probe.main(base + ["--reference-key", "Fotos_Perfil/public/x/y.jpg", "--other-reference-key", OTHER_KEY]) == 2
    assert probe.main(base + ["--reference-key", OWN_KEY, "--other-reference-key", OWN_KEY]) == 2
    assert probe.main(["--email", EMAIL, "--upload-url", "http://u.test/x", "--reference-key", OWN_KEY,
                       "--other-reference-key", OTHER_KEY]) == 2
    assert EMAIL not in capsys.readouterr().err
