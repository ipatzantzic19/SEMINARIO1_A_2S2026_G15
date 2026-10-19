"""Pruebas de contrato contra docs/api/openapi.yaml (fuente de verdad).

Se valida con openapi-core cada respuesta que el contrato declara para las
rutas implementadas: /health (200/503), /translations y /bot/messages
(200/400/403/429/503), /auth/register, /auth/confirm, /auth/login, /me y
/me/complete-profile (PRO-14), y las respuestas de error ya implementadas
(400, 401, 403). Las respuestas 501 NOT_IMPLEMENTED son transitorias y
exclusivas de Python: NO se validan contra el contrato. Las respuestas que
Python devuelve y el contrato no declara (p. ej. 429/503 en /auth/*) se
validan contra el esquema Error y están listadas en python-auth.md §10.
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

from app.common.errors import ApiError
from app.config import LexSettings
from app.modules.integrations.cognito.gateway import SignUpResult
from app.modules.integrations.lex.service import BotService
from app.modules.integrations.s3.objects import ObjectInfo
from app.modules.integrations.translate.service import TranslationService
from tests.conftest import COMPLETE_DPI, COMPLETE_SUB, INCOMPLETE_SUB, FakeDatabase, running, seeded_users
from tests.fakes import FakeCognito, FakeImageObjects, challenge, tokens

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
    # PATCH /me exige perfil completo (403 antes que 400); el 400 se prueba con uno completo.
    ("patch", "/me", {"fullName": "Ana"}, COMPLETE_SUB),
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
    ("post", "/bot/messages", {"text": "Hola", "sessionId": "s1"}),
]


@pytest.mark.parametrize(("method", "path", "payload"), FORBIDDEN_CASES, ids=[p for _, p, _ in FORBIDDEN_CASES])
def test_403_incomplete_profile_matches_contract(api: TestClient, auth_header, method: str, path: str, payload: Any) -> None:
    url = BASE_PATH + path
    response = api.request(method.upper(), url, json=payload, headers=auth_header(INCOMPLETE_SUB))
    assert response.status_code == 403
    validate(response, method, url, b"{}" if payload else None)


@pytest.mark.parametrize("payload", [{"fullName": "Ana"}, {"fullName": "A"}], ids=["valid-body", "invalid-body"])
def test_patch_me_incomplete_profile_is_403_before_body_validation(api: TestClient, auth_header, payload: dict) -> None:
    """Decisión PRO-14: contract.md limita al perfil incompleto a GET /me y
    complete-profile. openapi.yaml no declara 403 en PATCH /me (pedido a Isai
    en python-auth.md), por eso se valida solo contra el esquema Error."""
    response = api.patch(BASE_PATH + "/me", json=payload, headers=auth_header(INCOMPLETE_SUB))
    assert response.status_code == 403
    ERROR_SCHEMA.validate(response.json())
    assert response.json()["details"] == {"reason": "PROFILE_INCOMPLETE"}


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


# --- 7. POST /bot/messages (PRO-19) -----------------------------------------

LEX = LexSettings(region="us-east-1", bot_id="ABCDEFGHIJ", bot_alias_id="KLMNOPQRST")


class _LexDouble:
    def __init__(self, error: Exception | None = None, messages: list[dict[str, str]] | None = None) -> None:
        self.error = error
        self.messages = [{"contentType": "PlainText", "content": "Respuesta"}] if messages is None else messages

    def recognize_text(self, **kwargs: Any) -> dict[str, Any]:
        if self.error:
            raise self.error
        return {"messages": self.messages, "sessionId": kwargs["sessionId"]}


def _lex_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "interno"}}, "RecognizeText")


BOT_CASES = [
    ("200", LEX, _LexDouble(), {"text": "Hola", "sessionId": "s1"}, 200),
    ("200 sin mensajes", LEX, _LexDouble(messages=[]), {"text": "Hola", "sessionId": "s1"}, 200),
    ("400 solo espacios", LEX, _LexDouble(), {"text": "   ", "sessionId": "s1"}, 400),
    ("429 throttling", LEX, _LexDouble(_lex_error("ThrottlingException")), {"text": "Hola", "sessionId": "s1"}, 429),
    ("429 conflict", LEX, _LexDouble(_lex_error("ConflictException")), {"text": "Hola", "sessionId": "s1"}, 429),
    ("503 AWS", LEX, _LexDouble(_lex_error("ResourceNotFoundException")), {"text": "Hola", "sessionId": "s1"}, 503),
    ("503 sin bot", LexSettings(region="us-east-1"), _LexDouble(), {"text": "Hola", "sessionId": "s1"}, 503),
]


@pytest.mark.parametrize(
    ("settings", "double", "payload", "status"), [c[1:] for c in BOT_CASES], ids=[c[0] for c in BOT_CASES]
)
def test_bot_messages_responses_match_contract(build_app, auth_header, settings, double, payload: dict, status: int) -> None:
    url = BASE_PATH + "/bot/messages"
    with running(build_app(bot_service=BotService(settings, lambda: double))) as client:
        response = client.post(url, json=payload, headers=auth_header())
    assert response.status_code == status, response.text
    assert str(status) in SPEC["paths"]["/bot/messages"]["post"]["responses"]
    validate(response, "post", url, b"{}")


# --- 8. Registro, login y perfil (PRO-14) -----------------------------------

NEW_SUB = "44444444-4444-4444-8444-444444444444"
NEW_USER = {"fullName": "Carla Nueva", "email": "carla@example.com", "dpi": "3333333333333", "password": "ClaveSegura123!"}
FILE = "0b6f6c4e-873e-486a-847e-aeaf52aa4e2e.jpg"
OWN_KEY = f"Fotos_Perfil/public/{INCOMPLETE_SUB}/{FILE}"
JPEG = ObjectInfo("image/jpeg", 1000)


def _signed_up(c, i, u, t) -> None:
    c.sign_up_result = SignUpResult(sub=NEW_SUB, confirmed=False)


def _sign_up_error(error: ApiError):
    def setup(c, i, u, t) -> None:
        c.sign_up_result = error

    return setup


def _confirm_error(error: ApiError):
    def setup(c, i, u, t) -> None:
        c.confirm_error = error

    return setup


def _auth(result_for):
    def setup(c, i, u, t) -> None:
        c.auth_results = [result_for(t)]

    return setup


def _uploaded(c, i, u, t) -> None:
    i.objects[OWN_KEY] = JPEG
    i.objects[f"Fotos_Perfil/references/{INCOMPLETE_SUB}/{FILE}"] = JPEG


def _rds_down(c, i, u, t) -> None:
    u.fail_with = ConnectionError("rds caído")


def _nothing(c, i, u, t) -> None:
    return None


WRONG_PASSWORD = ApiError(400, "VALIDATION_ERROR", "x", {"reason": "INVALID_CURRENT_PASSWORD"})
PATCH_OK = {"currentPassword": "ClaveActual123!", "fullName": "Ana Editada"}

# (id, preparación, método, ruta, cuerpo, sub del Bearer, estado esperado)
PRO14_CASES = [
    ("register-201", _signed_up, "post", "/auth/register", NEW_USER, None, 201),
    ("register-400-policy", _nothing, "post", "/auth/register", {**NEW_USER, "password": "sinmayuscula1!"}, None, 400),
    ("register-409-rds", _signed_up, "post", "/auth/register", {**NEW_USER, "dpi": COMPLETE_DPI}, None, 409),
    ("register-409-cognito", _sign_up_error(ApiError(409, "CONFLICT", "x", {"reason": "EMAIL_TAKEN"})), "post", "/auth/register", NEW_USER, None, 409),
    ("register-429", _sign_up_error(ApiError(429, "RATE_LIMITED")), "post", "/auth/register", NEW_USER, None, 429),
    ("register-503", _nothing, "post", "/auth/register", NEW_USER, None, 503),
    ("confirm-204", _nothing, "post", "/auth/confirm", {"email": "a@example.com", "code": "123456"}, None, 204),
    ("confirm-400", _confirm_error(ApiError(400, "VALIDATION_ERROR", "x", {"reason": "CODE_MISMATCH"})), "post", "/auth/confirm", {"email": "a@example.com", "code": "123456"}, None, 400),
    ("confirm-404", _confirm_error(ApiError(404, "NOT_FOUND")), "post", "/auth/confirm", {"email": "a@example.com", "code": "123456"}, None, 404),
    ("confirm-429", _confirm_error(ApiError(429, "RATE_LIMITED")), "post", "/auth/confirm", {"email": "a@example.com", "code": "123456"}, None, 429),
    ("login-200", _auth(lambda t: tokens(t(COMPLETE_SUB))), "post", "/auth/login", {"email": "a@example.com", "password": "ClaveSegura123!"}, None, 200),
    ("login-202", _auth(lambda t: challenge()), "post", "/auth/login", {"email": "a@example.com", "password": "ClaveSegura123!"}, None, 202),
    ("login-401", _auth(lambda t: ApiError(401, "UNAUTHENTICATED", "x", {"reason": "USER_NOT_CONFIRMED"})), "post", "/auth/login", {"email": "a@example.com", "password": "ClaveSegura123!"}, None, 401),
    ("login-503", _nothing, "post", "/auth/login", {"email": "a@example.com", "password": "ClaveSegura123!"}, None, 503),
    ("me-200", _nothing, "get", "/me", None, COMPLETE_SUB, 200),
    ("me-200-incomplete", _nothing, "get", "/me", None, INCOMPLETE_SUB, 200),
    ("me-503", _rds_down, "get", "/me", None, COMPLETE_SUB, 503),
    ("patch-200", _auth(lambda t: tokens(t(COMPLETE_SUB))), "patch", "/me", PATCH_OK, COMPLETE_SUB, 200),
    ("patch-400-password", _auth(lambda t: WRONG_PASSWORD), "patch", "/me", PATCH_OK, COMPLETE_SUB, 400),
    ("patch-409-dpi", _auth(lambda t: tokens(t(COMPLETE_SUB))), "patch", "/me", {**PATCH_OK, "dpi": "2222222222222"}, COMPLETE_SUB, 409),
    ("patch-503", _nothing, "patch", "/me", PATCH_OK, COMPLETE_SUB, 503),
    ("complete-200", _uploaded, "post", "/me/complete-profile", {"profileImageKey": OWN_KEY}, INCOMPLETE_SUB, 200),
    ("complete-400", _nothing, "post", "/me/complete-profile", {"profileImageKey": OWN_KEY}, INCOMPLETE_SUB, 400),
    ("complete-403", _nothing, "post", "/me/complete-profile", {"profileImageKey": f"Fotos_Perfil/public/{COMPLETE_SUB}/{FILE}"}, INCOMPLETE_SUB, 403),
    ("complete-409", _nothing, "post", "/me/complete-profile", {"profileImageKey": OWN_KEY}, COMPLETE_SUB, 409),
    ("complete-503", _rds_down, "post", "/me/complete-profile", {"profileImageKey": OWN_KEY}, INCOMPLETE_SUB, 503),
]


@pytest.mark.parametrize(
    ("setup", "method", "path", "payload", "sub", "status"),
    [c[1:] for c in PRO14_CASES],
    ids=[c[0] for c in PRO14_CASES],
)
def test_pro14_responses_match_contract(build_app, auth_header, make_token, setup, method, path, payload, sub, status) -> None:
    cognito, images, users = FakeCognito(), FakeImageObjects(), seeded_users()
    setup(cognito, images, users, make_token)
    url = BASE_PATH + path
    headers = auth_header(sub) if sub else {}
    with running(build_app(cognito_gateway=cognito, image_objects=images, users_repository=users)) as client:
        response = client.request(method.upper(), url, json=payload, headers=headers)
    assert response.status_code == status, response.text

    declared = SPEC["paths"][path][method]["responses"]
    if str(status) in declared:
        validate(response, method, url, b"{}" if payload is not None else None)
    else:
        # No declarado en openapi.yaml (pedido a Isai en python-auth.md §10).
        assert status in (429, 503), f"{status} no declarado en {method.upper()} {path}"
        ERROR_SCHEMA.validate(response.json())
