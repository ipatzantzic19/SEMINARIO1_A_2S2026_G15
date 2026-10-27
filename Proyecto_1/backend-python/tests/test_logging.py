"""Los logs no exponen tokens, contraseñas, imágenes ni secretos."""

from __future__ import annotations

import io
import json
import logging

import pytest

from app.common.logs import build_handler, redact
from tests.conftest import running

JWT_LIKE = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJhLWRlLXBydWViYQ"


@pytest.mark.parametrize(
    ("raw", "forbidden"),
    [
        (f"Authorization: Bearer {JWT_LIKE}", JWT_LIKE),
        (f"token suelto {JWT_LIKE}", JWT_LIKE),
        ('{"password": "hunter2-secret"}', "hunter2-secret"),
        ("currentPassword=otra-clave", "otra-clave"),
        ("refreshToken: abc.def.ghi", "abc.def.ghi"),
        ("postgresql://app:Pa55word@db:5432/semisocial", "Pa55word"),
        ("foto data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB", "iVBORw0KGgo"),
        ("blob " + "A" * 400, "A" * 400),
    ],
)
def test_redact(raw: str, forbidden: str) -> None:
    assert forbidden not in redact(raw)


@pytest.fixture
def log_stream():
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


def test_request_logs_are_sanitized(build_app, make_token, log_stream) -> None:
    token = make_token()
    with running(build_app()) as client:
        client.post(
            "/api/v1/auth/login?token=query-secret",
            json={"email": "ana@example.com", "password": "MiClaveSecreta123!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        client.get("/api/v1/me", headers={"Authorization": "Bearer token-falso-xyz"})

    output = log_stream.getvalue()
    assert output, "se esperaba al menos un registro"
    for secret in (token, "MiClaveSecreta123!", "query-secret", "token-falso-xyz", "ana@example.com"):
        assert secret not in output

    records = [json.loads(line) for line in output.splitlines()]
    access = [r for r in records if r.get("event") == "request"]
    assert {"method", "path", "status", "durationMs", "requestId"} <= set(access[0])
    assert all("?" not in r["path"] for r in access)


def test_unhandled_exception_log_omits_exception_message(build_app, log_stream) -> None:
    app = build_app()

    def boom() -> None:
        raise RuntimeError("password=hunter2 dpi=1234567890123")

    app.add_api_route("/api/v1/__boom", boom)
    with running(app) as client:
        client.get("/api/v1/__boom")

    output = log_stream.getvalue()
    assert "unhandled_exception" in output
    assert "RuntimeError" in output
    assert "hunter2" not in output and "1234567890123" not in output
