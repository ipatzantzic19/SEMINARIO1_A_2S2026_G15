"""Pruebas de contrato contra docs/api/openapi.yaml (fuente de verdad).

Se valida con openapi-core cada respuesta que el contrato declara para las
rutas implementadas: /health (200/503), /translations (200/400/403/429/503)
y las respuestas de error ya implementadas (400, 401, 403). Las respuestas 501 NOT_IMPLEMENTED son
transitorias y exclusivas de Python: NO se validan contra el contrato.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlsplit

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from openapi_core import OpenAPI
from openapi_core.datatypes import RequestParameters
from werkzeug.datastructures import Headers, ImmutableMultiDict

from botocore.exceptions import ClientError, EndpointConnectionError

from app.modules.integrations.translate.service import TranslationService
from tests.conftest import COMPLETE_SUB, INCOMPLETE_SUB, FakeDatabase, running

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
OPENAPI = OpenAPI.from_file_path(str(SPEC_PATH))
BASE_PATH = SPEC["servers"][0]["url"]  # /api/v1
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
# Vive en API Gateway + Lambda (PRO-11), no en los backends.
NOT_IN_BACKEND = {"uploadImage"}
UUID_SAMPLE = "596bdc55-48ac-47b9-a93d-fd15b7646db5"


# --- adaptadores mínimos para openapi-core --------------------------------


class _Request:
    def __init__(self, method: str, url: str, body: bytes | None, content_type: str) -> None:
        parts = urlsplit(url)
        self.host_url = "http://testserver"
        self.path = parts.path
        self.method = method.lower()
        self.body = body
        self.content_type = content_type
        self.parameters = RequestParameters(
            query=ImmutableMultiDict(parse_qsl(parts.query)), header=Headers(), cookie=ImmutableMultiDict()
        )


class _Response:
    def __init__(self, response: Any) -> None:
        self.data = response.content
        self.status_code = response.status_code
        self.content_type = response.headers.get("content-type", "application/json")
        self.headers = Headers(dict(response.headers))


def validate(response: Any, method: str, url: str, body: bytes | None = None) -> None:
    assert response.status_code != 501, "501 es transitorio; no se valida contra el contrato"
    OPENAPI.validate_response(_Request(method, url, body, "application/json"), _Response(response))


# --- inventario de operaciones del contrato -------------------------------


def operations() -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in SPEC["paths"].items():
        for method in HTTP_METHODS:
            if method in item and item[method]["operationId"] not in NOT_IN_BACKEND:
                yield method, path, item[method]


def full_path(path: str, operation: dict[str, Any]) -> str:
    servers = operation.get("servers")
    prefix = "" if servers and servers[0]["url"] == "/" else BASE_PATH
    return prefix + path


def concrete(path: str) -> str:
    for name in ("{postId}", "{challengeId}", "{requestId}", "{friendId}"):
        path = path.replace(name, UUID_SAMPLE)
    return path


def is_protected(operation: dict[str, Any]) -> bool:
    security = operation.get("security", SPEC.get("security", []))
    return any("bearerAuth" in s for s in security)


ALL_OPERATIONS = list(operations())


@pytest.fixture
def app(build_app):
    return build_app()


@pytest.fixture
def api(app) -> Iterator[TestClient]:
    with running(app) as client:
        yield client


# --- 1. Paridad de rutas --------------------------------------------------


def _routed_operations(app) -> dict[tuple[str, str], str]:
    # Inventario de rutas reales de la app (FastAPI incluye routers de forma
    # diferida, por eso se usa su esquema generado solo como índice de rutas).
    return {
        (method, path): op["operationId"]
        for path, item in app.openapi()["paths"].items()
        for method, op in item.items()
    }


def test_every_contract_operation_is_routed_with_same_method_and_path(app) -> None:
    routed = set(_routed_operations(app))
    expected = {(method, full_path(path, op)) for method, path, op in ALL_OPERATIONS}
    assert expected - routed == set(), "faltan operaciones del contrato"
    assert routed - expected == set(), "hay rutas fuera del contrato"


def test_operation_ids_match_contract(app) -> None:
    routed = _routed_operations(app)
    for method, path, op in ALL_OPERATIONS:
        assert routed[(method, full_path(path, op))] == op["operationId"]


# --- 2. /health -----------------------------------------------------------


def test_health_200_matches_contract(api: TestClient) -> None:
    response = api.get("/health")
    validate(response, "get", "/health")


def test_health_503_matches_contract(build_app) -> None:
    with running(build_app(FakeDatabase(healthy=False))) as client:
        response = client.get("/health")
    assert response.status_code == 503
    validate(response, "get", "/health")


# --- 3. 401 en todas las operaciones protegidas ---------------------------

PROTECTED = [(m, p, op) for m, p, op in ALL_OPERATIONS if is_protected(op)]


@pytest.mark.parametrize(
    ("method", "path", "operation"),
    [(m, p, op) for m, p, op in PROTECTED if "401" in op["responses"]],
    ids=lambda v: v["operationId"] if isinstance(v, dict) else None,
)
def test_401_matches_contract(api: TestClient, method: str, path: str, operation: dict[str, Any]) -> None:
    url = concrete(full_path(path, operation))
    response = api.request(method.upper(), url, json={} if method != "get" else None)
    assert response.status_code == 401
    validate(response, method, url, b"{}" if method != "get" else None)


ERROR_SCHEMA = Draft202012Validator(SPEC["components"]["schemas"]["Error"])
UNDECLARED_401 = [(m, p, op) for m, p, op in PROTECTED if "401" not in op["responses"]]


@pytest.mark.parametrize(
    ("method", "path", "operation"),
    UNDECLARED_401,
    ids=lambda v: v["operationId"] if isinstance(v, dict) else None,
)
def test_401_on_operations_without_declared_401_uses_error_schema(
    api: TestClient, method: str, path: str, operation: dict[str, Any]
) -> None:
    """Hueco del contrato (ver python.md): estas operaciones no declaran 401."""
    response = api.request(method.upper(), concrete(full_path(path, operation)), json={} if method != "get" else None)
    assert response.status_code == 401
    ERROR_SCHEMA.validate(response.json())


# --- 4. 400 VALIDATION_ERROR ----------------------------------------------

INVALID_BODIES: list[tuple[str, str, dict[str, Any], str | None]] = [
    ("post", "/auth/register", {"fullName": "A", "email": "x", "dpi": "1", "password": "corta"}, None),
    ("post", "/auth/confirm", {"email": "ana@example.com", "code": "1"}, None),
    ("post", "/auth/login", {"email": "no-es-correo"}, None),
    ("post", "/auth/face/challenges", {}, None),
    ("post", f"/auth/face/challenges/{UUID_SAMPLE}/verify", {}, None),
    ("patch", "/me", {"fullName": "Ana"}, INCOMPLETE_SUB),
    ("post", "/me/complete-profile", {}, INCOMPLETE_SUB),
    ("post", "/friend-requests", {"addresseeId": "no-uuid"}, COMPLETE_SUB),
    ("patch", f"/friend-requests/{UUID_SAMPLE}", {"decision": "maybe"}, COMPLETE_SUB),
    ("post", "/posts", {"description": "x" * 2001}, COMPLETE_SUB),
    ("post", f"/posts/{UUID_SAMPLE}/comments", {"body": ""}, COMPLETE_SUB),
    ("post", "/translations", {"text": "Hola", "targetLanguage": "it"}, COMPLETE_SUB),
    ("post", "/bot/messages", {"text": "", "sessionId": "s"}, COMPLETE_SUB),
]


@pytest.mark.parametrize(("method", "path", "payload", "sub"), INVALID_BODIES, ids=[p for _, p, _, _ in INVALID_BODIES])
def test_400_matches_contract(api: TestClient, auth_header, method: str, path: str, payload: dict, sub: str | None) -> None:
    url = BASE_PATH + path
    headers = auth_header(sub) if sub else {}
    response = api.request(method.upper(), url, json=payload, headers=headers)
    assert response.status_code == 400, response.text
    validate(response, method, url, b"{}")


@pytest.mark.parametrize("query", ["limit=0", "limit=51"])
def test_400_on_pagination_matches_contract(api: TestClient, auth_header, query: str) -> None:
    url = f"{BASE_PATH}/posts?{query}"
    response = api.get(url, headers=auth_header())
    assert response.status_code == 400
    validate(response, "get", f"{BASE_PATH}/posts")


# --- 5. 403 por perfil incompleto -----------------------------------------

FORBIDDEN_CASES = [
    ("get", f"/posts/{UUID_SAMPLE}/comments", None),
    ("post", f"/posts/{UUID_SAMPLE}/comments", {"body": "hola"}),
    ("patch", f"/friend-requests/{UUID_SAMPLE}", {"decision": "accepted"}),
    ("get", f"/conversations/{UUID_SAMPLE}/messages", None),
    ("post", "/translations", {"text": "Hola", "targetLanguage": "en"}),
]


@pytest.mark.parametrize(("method", "path", "payload"), FORBIDDEN_CASES, ids=[p for _, p, _ in FORBIDDEN_CASES])
def test_403_incomplete_profile_matches_contract(api: TestClient, auth_header, method: str, path: str, payload: Any) -> None:
    url = BASE_PATH + path
    response = api.request(method.upper(), url, json=payload, headers=auth_header(INCOMPLETE_SUB))
    assert response.status_code == 403
    validate(response, method, url, b"{}" if payload else None)


# --- 6. POST /translations (PRO-18) -----------------------------------------


class _TranslateDouble:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def translate_text(self, **kwargs: Any) -> dict[str, Any]:
        if self.error:
            raise self.error
        return {"TranslatedText": "Hello", "SourceLanguageCode": "es", "TargetLanguageCode": kwargs["TargetLanguageCode"]}


def _aws_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "interno"}}, "TranslateText")


TRANSLATION_CASES = [
    ("200", None, {"text": "Hola", "targetLanguage": "en"}, 200),
    ("200 mismo idioma", None, {"text": "Hola", "sourceLanguage": "es", "targetLanguage": "es"}, 200),
    ("400 solo espacios", None, {"text": "   ", "targetLanguage": "en"}, 400),
    ("400 bytes", None, {"text": "😀" * 2501, "targetLanguage": "en"}, 400),
    ("400 baja confianza", _aws_error("DetectedLanguageLowConfidenceException"), {"text": "ok", "targetLanguage": "en"}, 400),
    ("429", _aws_error("ThrottlingException"), {"text": "Hola", "targetLanguage": "en"}, 429),
    ("503 AWS", _aws_error("ServiceUnavailableException"), {"text": "Hola", "targetLanguage": "en"}, 503),
    ("503 red", EndpointConnectionError(endpoint_url="https://translate"), {"text": "Hola", "targetLanguage": "en"}, 503),
]


@pytest.mark.parametrize(
    ("error", "payload", "status"), [c[1:] for c in TRANSLATION_CASES], ids=[c[0] for c in TRANSLATION_CASES]
)
def test_translations_responses_match_contract(build_app, auth_header, error, payload: dict, status: int) -> None:
    double = _TranslateDouble(error)
    url = BASE_PATH + "/translations"
    with running(build_app(translation_service=TranslationService(lambda: double))) as client:
        response = client.post(url, json=payload, headers=auth_header())
    assert response.status_code == status, response.text
    assert str(status) in SPEC["paths"]["/translations"]["post"]["responses"]
    validate(response, "post", url, b"{}")
