"""Esquema común de errores para validación, rutas, 500 y rutas pendientes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import assert_error, running

VALID_REGISTER = {
    "fullName": "Ana Prueba",
    "email": "Ana@Example.com",
    "dpi": "1234567890123",
    "password": "Password123!",
}


def test_validation_error_is_400_not_422(client: TestClient) -> None:
    body = assert_error(client.post("/api/v1/auth/register", json={}), 400, "VALIDATION_ERROR")
    fields = {f["field"] for f in body["details"]["fields"]}
    assert {"fullName", "email", "dpi", "password"} <= fields


def test_validation_details_do_not_echo_input(client: TestClient) -> None:
    payload = {**VALID_REGISTER, "password": "corta", "dpi": "12ab"}
    response = client.post("/api/v1/auth/register", json=payload)
    assert_error(response, 400, "VALIDATION_ERROR")
    assert "corta" not in response.text
    assert "12ab" not in response.text


def test_malformed_json_is_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", content=b"{no-json", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 400, "VALIDATION_ERROR")


def test_invalid_uuid_path_parameter(client: TestClient, auth_header) -> None:
    response = client.get("/api/v1/posts/no-es-uuid/comments", headers=auth_header())
    assert_error(response, 400, "VALIDATION_ERROR")


def test_limit_outside_range(client: TestClient, auth_header) -> None:
    assert_error(client.get("/api/v1/posts?limit=51", headers=auth_header()), 400, "VALIDATION_ERROR")
    assert_error(client.get("/api/v1/users?limit=0", headers=auth_header()), 400, "VALIDATION_ERROR")


def test_translation_rejects_unsupported_language(client: TestClient, auth_header) -> None:
    response = client.post(
        "/api/v1/translations", json={"text": "Hola", "targetLanguage": "it"}, headers=auth_header()
    )
    assert_error(response, 400, "VALIDATION_ERROR")


def test_unknown_route_and_method(client: TestClient) -> None:
    assert_error(client.get("/api/v1/no-existe"), 404, "NOT_FOUND")
    assert_error(client.delete("/health"), 405, "METHOD_NOT_ALLOWED")


def test_pending_route_returns_501_with_ticket(client: TestClient) -> None:
    # Login facial fuera de alcance de PRO-14 (docs/api/python-auth.md §8).
    response = client.post("/api/v1/auth/face/challenges", json={"email": "ana@example.com"})
    body = assert_error(response, 501, "NOT_IMPLEMENTED")
    assert body["details"] == {"ticket": "PRO-31", "operationId": "createFaceChallenge"}


def test_unhandled_exception_returns_generic_500(build_app, capsys) -> None:
    app = build_app()

    def boom() -> None:
        raise RuntimeError("detalle interno: tabla users password=hunter2")

    app.add_api_route("/api/v1/__boom", boom)
    with running(app) as test_client:
        response = test_client.get("/api/v1/__boom")
    body = assert_error(response, 500, "INTERNAL_SERVER_ERROR")
    assert body["message"] == "Error interno del servidor."
    assert "hunter2" not in response.text and "tabla" not in response.text


def test_request_id_is_propagated_or_regenerated(client: TestClient) -> None:
    ok = client.get("/api/v1/me", headers={"X-Request-Id": "abc-123"})
    assert ok.headers["x-request-id"] == "abc-123"
    assert ok.json()["requestId"] == "abc-123"

    unsafe = client.get("/api/v1/me", headers={"X-Request-Id": "x" * 300})
    assert unsafe.headers["x-request-id"] != "x" * 300
