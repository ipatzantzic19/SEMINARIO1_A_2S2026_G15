"""GET /health: mismo formato que Node, en la raíz, sin autenticación."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import DatabaseUnavailable
from tests.conftest import FakeDatabase, assert_error, local_settings, running


def test_health_matches_node_format(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "python", "version": "1.0.0"}
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-request-id"]


def test_health_ignores_authorization_header(client: TestClient) -> None:
    response = client.get("/health", headers={"Authorization": "Bearer basura"})
    assert response.status_code == 200


def test_health_is_not_under_base_path(client: TestClient) -> None:
    assert_error(client.get("/api/v1/health"), 404, "NOT_FOUND")


def test_health_returns_503_when_database_is_down(build_app) -> None:
    with running(build_app(FakeDatabase(healthy=False))) as test_client:
        body = assert_error(test_client.get("/health"), 503, "SERVICE_UNAVAILABLE")
    assert body["details"] is None


def test_health_without_database_configured_in_local(build_app) -> None:
    with running(build_app(FakeDatabase(configured=False, healthy=False))) as test_client:
        assert test_client.get("/health").status_code == 200


def test_startup_opens_database_as_required_only_in_production(build_app) -> None:
    database = FakeDatabase()
    with running(build_app(database)):
        assert database.opened_with is False
    assert database.closed


def test_startup_fails_when_production_database_is_unavailable(build_app) -> None:
    class DownDatabase(FakeDatabase):
        def open(self, *, required: bool) -> None:
            raise DatabaseUnavailable("No fue posible conectar a PostgreSQL (db:5432/semisocial): OperationalError.")

    app = build_app(DownDatabase(), settings=local_settings())
    with pytest.raises(DatabaseUnavailable):
        with TestClient(app):
            pass


def test_swagger_only_in_local(build_app) -> None:
    from tests.test_config import PRODUCTION_ENV
    from app.config import Settings

    with running(build_app()) as local_client:
        assert local_client.get("/api/docs").status_code == 200
    with running(build_app(settings=Settings.from_env(PRODUCTION_ENV))) as prod_client:
        assert_error(prod_client.get("/api/docs"), 404, "NOT_FOUND")
        assert_error(prod_client.get("/api/openapi.json"), 404, "NOT_FOUND")
