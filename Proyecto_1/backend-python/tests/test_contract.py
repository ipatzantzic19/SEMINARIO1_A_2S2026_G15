"""Pruebas de contrato contra docs/api/openapi.yaml (fuente de verdad).

Se valida con openapi-core cada respuesta que el contrato declara para las
rutas implementadas: /health (200/503), /translations y /bot/messages
(200/400/403/429/503), /auth/register, /auth/confirm, /auth/confirm/resend, /auth/login, /me y
/me/complete-profile (PRO-14), y las respuestas de error ya implementadas
(400, 401, 403), y las rutas sociales de PRO-15 (/users, /friend-requests,
/friends: 200/201/400/401/403/404/409/503). Las respuestas 501 NOT_IMPLEMENTED son transitorias y
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


def test_openapi_document_is_valid() -> None:
    from openapi_spec_validator import validate as validate_spec

    validate_spec(SPEC)


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
    ("post", "/auth/confirm/resend", {"email": "no-es-correo"}, None),
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


def _resend_error(error: ApiError):
    def setup(c, i, u, t) -> None:
        c.resend_error = error

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
    ("resend-204", _nothing, "post", "/auth/confirm/resend", {"email": "a@example.com"}, None, 204),
    ("resend-204-unknown-email", _resend_error(ApiError(404, "NOT_FOUND", None, {"reason": "RESEND_NOT_ALLOWED"})), "post", "/auth/confirm/resend", {"email": "a@example.com"}, None, 204),
    ("resend-429", _resend_error(ApiError(429, "RATE_LIMITED")), "post", "/auth/confirm/resend", {"email": "a@example.com"}, None, 429),
    ("resend-503", _resend_error(ApiError(503, "SERVICE_UNAVAILABLE")), "post", "/auth/confirm/resend", {"email": "a@example.com"}, None, 503),
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


# --- 9. /users, /friend-requests y /friends (PRO-15) ---------------------------------

from types import SimpleNamespace  # noqa: E402

from tests.fakes import InMemoryFriendsRepository  # noqa: E402
from tests.test_friends import A_ID, A_SUB, B_ID, B_SUB, C_ID, C_SUB, D_SUB, UNKNOWN_ID, _seed  # noqa: E402


@pytest.fixture
def social(build_app):
    users = _seed()
    friends = InMemoryFriendsRepository(users)
    with running(build_app(users_repository=users, friends_repository=friends)) as client:
        yield SimpleNamespace(client=client, friends=friends)


def _social_call(social, auth_header, method: str, path: str, sub: str, payload: Any = None):
    url = BASE_PATH + path
    response = social.client.request(method.upper(), url, json=payload, headers=auth_header(sub))
    return response, url


def _check_declared(response, method: str, spec_path: str, url: str, payload: Any, status: int) -> None:
    assert response.status_code == status, response.text
    assert str(status) in SPEC["paths"][spec_path][method]["responses"], f"{status} no declarado"
    validate(response, method, url, b"{}" if payload is not None else None)


def test_social_success_responses_match_contract(social, auth_header) -> None:
    response, url = _social_call(social, auth_header, "get", "/users", A_SUB)
    _check_declared(response, "get", "/users", url, None, 200)

    payload = {"addresseeId": B_ID}
    response, url = _social_call(social, auth_header, "post", "/friend-requests", A_SUB, payload)
    _check_declared(response, "post", "/friend-requests", url, payload, 201)
    request_id = response.json()["requestId"]

    response, url = _social_call(social, auth_header, "get", "/friend-requests", B_SUB)
    _check_declared(response, "get", "/friend-requests", url, None, 200)

    payload = {"decision": "accepted"}
    response, url = _social_call(social, auth_header, "patch", f"/friend-requests/{request_id}", B_SUB, payload)
    _check_declared(response, "patch", "/friend-requests/{requestId}", url, payload, 200)

    response, url = _social_call(social, auth_header, "get", "/friends", A_SUB)
    _check_declared(response, "get", "/friends", url, None, 200)
    assert response.json()[0]["userId"] == B_ID

    # Rechazo: mismo esquema FriendRequest con status "rejected".
    payload = {"addresseeId": C_ID}
    response, url = _social_call(social, auth_header, "post", "/friend-requests", A_SUB, payload)
    second_id = response.json()["requestId"]
    payload = {"decision": "rejected"}
    response, url = _social_call(social, auth_header, "patch", f"/friend-requests/{second_id}", C_SUB, payload)
    _check_declared(response, "patch", "/friend-requests/{requestId}", url, payload, 200)
    assert response.json()["status"] == "rejected"


def _pending_ab(social) -> str:
    return social.friends.create_request(A_ID, B_ID).id


SOCIAL_ERROR_CASES = [
    # (id, método, ruta del contrato, ruta concreta, cuerpo, sub, estado, prepara una solicitud A→B)
    ("post-400-auto", "post", "/friend-requests", "/friend-requests", {"addresseeId": A_ID}, A_SUB, 400, False),
    ("post-400-uuid", "post", "/friend-requests", "/friend-requests", {"addresseeId": "x"}, A_SUB, 400, False),
    ("post-403-incompleto", "post", "/friend-requests", "/friend-requests", {"addresseeId": B_ID}, D_SUB, 403, False),
    ("post-404", "post", "/friend-requests", "/friend-requests", {"addresseeId": UNKNOWN_ID}, A_SUB, 404, False),
    ("post-409-duplicada", "post", "/friend-requests", "/friend-requests", {"addresseeId": B_ID}, A_SUB, 409, True),
    ("post-409-cruzada", "post", "/friend-requests", "/friend-requests", {"addresseeId": A_ID}, B_SUB, 409, True),
    ("patch-400-decision", "patch", "/friend-requests/{requestId}", "/friend-requests/{id}", {"decision": "x"}, B_SUB, 400, True),
    ("patch-403-tercero", "patch", "/friend-requests/{requestId}", "/friend-requests/{id}", {"decision": "accepted"}, C_SUB, 403, True),
    ("patch-403-incompleto", "patch", "/friend-requests/{requestId}", "/friend-requests/{id}", {"decision": "accepted"}, D_SUB, 403, True),
    ("patch-404", "patch", "/friend-requests/{requestId}", f"/friend-requests/{UNKNOWN_ID}", {"decision": "accepted"}, B_SUB, 404, False),
    ("get-users-403", "get", "/users", "/users", None, D_SUB, 403, False),
    ("get-requests-403", "get", "/friend-requests", "/friend-requests", None, D_SUB, 403, False),
    ("get-friends-403", "get", "/friends", "/friends", None, D_SUB, 403, False),
]


@pytest.mark.parametrize(
    ("method", "spec_path", "path", "payload", "sub", "status", "prepare"),
    [c[1:] for c in SOCIAL_ERROR_CASES],
    ids=[c[0] for c in SOCIAL_ERROR_CASES],
)
def test_social_errors_match_contract(social, auth_header, method, spec_path, path, payload, sub, status, prepare) -> None:
    request_id = _pending_ab(social) if prepare else None
    response, url = _social_call(social, auth_header, method, path.replace("{id}", request_id or ""), sub, payload)
    _check_declared(response, method, spec_path, url, payload, status)


def test_patch_already_answered_matches_contract(social, auth_header) -> None:
    request_id = _pending_ab(social)
    payload = {"decision": "accepted"}
    path = f"/friend-requests/{request_id}"
    assert _social_call(social, auth_header, "patch", path, B_SUB, payload)[0].status_code == 200
    response, url = _social_call(social, auth_header, "patch", path, B_SUB, payload)
    _check_declared(response, "patch", "/friend-requests/{requestId}", url, payload, 400)
    assert response.json()["details"] == {"reason": "ALREADY_ANSWERED"}


SOCIAL_ROUTES = [
    ("get", "/users", "/users", None),
    ("get", "/friend-requests", "/friend-requests", None),
    ("post", "/friend-requests", "/friend-requests", {"addresseeId": B_ID}),
    ("patch", "/friend-requests/{requestId}", f"/friend-requests/{UNKNOWN_ID}", {"decision": "accepted"}),
    ("get", "/friends", "/friends", None),
]


@pytest.mark.parametrize(("method", "spec_path", "path", "payload"), SOCIAL_ROUTES, ids=[r[2][:24] for r in SOCIAL_ROUTES])
def test_social_rds_failure_matches_contract(social, auth_header, method, spec_path, path, payload) -> None:
    social.friends.fail_with = ConnectionError("rds caído")
    response, url = _social_call(social, auth_header, method, path, A_SUB, payload)
    _check_declared(response, method, spec_path, url, payload, 503)


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "cursor=no-es-un-cursor"])
def test_users_400_matches_contract(social, auth_header, query: str) -> None:
    """Límite o cursor inválidos: 400 declarado en GET /users (python-friends.md §10)."""
    response, url = _social_call(social, auth_header, "get", f"/users?{query}", A_SUB)
    _check_declared(response, "get", "/users", url, None, 400)
    ERROR_SCHEMA.validate(response.json())


# --- 10. /posts, /posts/{postId}/comments y /labels (PRO-34) ---------------------------

from tests.test_posts import A_ID as POSTS_A_ID  # noqa: E402,F401
from tests.test_posts import A_SUB as POSTS_A, B_SUB as POSTS_B, C_SUB as POSTS_C, D_SUB as POSTS_D  # noqa: E402
from tests.test_posts import upload as upload_post_image, world as posts_world  # noqa: E402,F401
from tests.fakes import label as fake_label  # noqa: E402


def _posts_call(world, auth_header, method: str, path: str, sub: str, payload: Any = None):
    url = BASE_PATH + path
    return world.client.request(method.upper(), url, json=payload, headers=auth_header(sub)), url


def _created_post(world, auth_header) -> str:
    key = upload_post_image(world, POSTS_A)
    response, _ = _posts_call(world, auth_header, "post", "/posts", POSTS_A, {"imageKey": key})
    return response.json()["postId"]


def test_posts_success_responses_match_contract(posts_world, auth_header) -> None:
    world = posts_world
    key = upload_post_image(world, POSTS_A, labels=[fake_label("perro", "98.12", "Dog")])
    payload = {"imageKey": key, "description": "Mi perro"}
    response, url = _posts_call(world, auth_header, "post", "/posts", POSTS_A, payload)
    _check_declared(response, "post", "/posts", url, payload, 201)
    post_id = response.json()["postId"]

    response, url = _posts_call(world, auth_header, "get", "/posts?limit=5&label=perro", POSTS_B)
    _check_declared(response, "get", "/posts", url, None, 200)
    assert [item["postId"] for item in response.json()["items"]] == [post_id]

    payload = {"body": "¡Qué buena foto!"}
    response, url = _posts_call(world, auth_header, "post", f"/posts/{post_id}/comments", POSTS_B, payload)
    _check_declared(response, "post", "/posts/{postId}/comments", url, payload, 201)

    response, url = _posts_call(world, auth_header, "get", f"/posts/{post_id}/comments", POSTS_A)
    _check_declared(response, "get", "/posts/{postId}/comments", url, None, 200)

    response, url = _posts_call(world, auth_header, "get", "/labels?q=pe", POSTS_B)
    _check_declared(response, "get", "/labels", url, None, 200)
    assert response.json() == [{"name": "perro", "postCount": 1}]


def test_posts_second_page_and_empty_feed_match_contract(posts_world, auth_header) -> None:
    world = posts_world
    for _ in range(3):
        _created_post(world, auth_header)
    response, url = _posts_call(world, auth_header, "get", "/posts?limit=2", POSTS_A)
    _check_declared(response, "get", "/posts", url, None, 200)
    cursor = response.json()["nextCursor"]
    response, url = _posts_call(world, auth_header, "get", f"/posts?limit=2&cursor={cursor}", POSTS_A)
    _check_declared(response, "get", "/posts", url, None, 200)
    assert response.json()["nextCursor"] is None
    response, url = _posts_call(world, auth_header, "get", "/posts", POSTS_C)  # sin amigos ni publicaciones
    _check_declared(response, "get", "/posts", url, None, 200)
    assert response.json() == {"items": [], "nextCursor": None}


def _fail_rekognition(error: ApiError):
    def prepare(world) -> dict[str, Any]:
        key = upload_post_image(world, POSTS_A, labels=error)
        return {"imageKey": key}

    return prepare


def _other_users_image(world) -> dict[str, Any]:
    return {"imageKey": upload_post_image(world, POSTS_B)}


def _missing_image(world) -> dict[str, Any]:
    return {"imageKey": f"Fotos_Publicadas/{POSTS_A}/3fa85f64-5717-4562-b3fc-2c963f66afa6.jpg"}


POSTS_CREATE_ERRORS = [
    ("400 sin imagen", lambda w: {"description": "sin imagen"}, POSTS_A, 400),
    ("400 clave inválida", lambda w: {"imageKey": "Fotos_Perfil/x.jpg"}, POSTS_A, 400),
    ("403 perfil incompleto", lambda w: {"imageKey": "Fotos_Publicadas/x"}, POSTS_D, 403),
    ("403 imagen ajena", _other_users_image, POSTS_A, 403),
    ("404 imagen inexistente", _missing_image, POSTS_A, 404),
    ("404 Rekognition", _fail_rekognition(ApiError(404, "NOT_FOUND", details={"reason": "IMAGE_NOT_FOUND"})), POSTS_A, 404),
    ("429 Rekognition", _fail_rekognition(ApiError(429, "RATE_LIMITED")), POSTS_A, 429),
    ("503 Rekognition", _fail_rekognition(ApiError(503, "SERVICE_UNAVAILABLE")), POSTS_A, 503),
]


@pytest.mark.parametrize(
    ("prepare", "sub", "status"), [c[1:] for c in POSTS_CREATE_ERRORS], ids=[c[0] for c in POSTS_CREATE_ERRORS]
)
def test_create_post_errors_match_contract(posts_world, auth_header, prepare, sub, status) -> None:
    payload = prepare(posts_world)
    response, url = _posts_call(posts_world, auth_header, "post", "/posts", sub, payload)
    _check_declared(response, "post", "/posts", url, payload, status)


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "cursor=no-es-un-cursor", "label=" + "a" * 101])
def test_feed_400_matches_contract(posts_world, auth_header, query: str) -> None:
    response, url = _posts_call(posts_world, auth_header, "get", f"/posts?{query}", POSTS_A)
    _check_declared(response, "get", "/posts", url, None, 400)
    ERROR_SCHEMA.validate(response.json())


def test_labels_400_matches_contract(posts_world, auth_header) -> None:
    response, url = _posts_call(posts_world, auth_header, "get", "/labels?q=" + "a" * 101, POSTS_A)
    _check_declared(response, "get", "/labels", url, None, 400)


def test_comment_errors_match_contract(posts_world, auth_header) -> None:
    world = posts_world
    post_id = _created_post(world, auth_header)
    path = f"/posts/{post_id}/comments"
    cases = [
        ("post", path, {"body": "   "}, POSTS_B, 400),
        ("post", path, {"body": "hola"}, POSTS_C, 403),  # ni autora ni amiga (NOT_FRIEND_OR_AUTHOR)
        ("post", f"/posts/{UUID_SAMPLE}/comments", {"body": "hola"}, POSTS_A, 404),
        ("post", path, {"body": "hola"}, POSTS_D, 403),  # perfil incompleto
        ("get", path, None, POSTS_C, 403),
        ("get", f"/posts/{UUID_SAMPLE}/comments", None, POSTS_A, 404),
        ("get", path, None, POSTS_D, 403),
    ]
    for method, route, payload, sub, status in cases:
        response, url = _posts_call(world, auth_header, method, route, sub, payload)
        _check_declared(response, method, "/posts/{postId}/comments", url, payload, status)
        if route == path and sub == POSTS_C:
            assert response.json()["details"] == {"reason": "NOT_FRIEND_OR_AUTHOR"}


def test_labels_and_feed_403_match_contract(posts_world, auth_header) -> None:
    for path, spec_path in (("/posts", "/posts"), ("/labels", "/labels")):
        response, url = _posts_call(posts_world, auth_header, "get", path, POSTS_D)
        _check_declared(response, "get", spec_path, url, None, 403)


POSTS_ROUTES = [
    ("get", "/posts", "/posts", None),
    ("post", "/posts", "/posts", "create"),
    ("get", "/labels", "/labels", None),
    ("get", f"/posts/{UUID_SAMPLE}/comments", "/posts/{postId}/comments", None),
    ("post", f"/posts/{UUID_SAMPLE}/comments", "/posts/{postId}/comments", {"body": "hola"}),
]


@pytest.mark.parametrize(("method", "path", "spec_path", "payload"), POSTS_ROUTES, ids=[r[0] + r[1][:28] for r in POSTS_ROUTES])
def test_posts_rds_failure_matches_contract(posts_world, auth_header, method, path, spec_path, payload) -> None:
    if payload == "create":
        payload = {"imageKey": upload_post_image(posts_world, POSTS_A)}
    posts_world.posts.fail_with = ConnectionError("rds caído")
    response, url = _posts_call(posts_world, auth_header, method, path, POSTS_A, payload)
    _check_declared(response, method, spec_path, url, payload, 503)


@pytest.mark.parametrize(("method", "path", "spec_path", "payload"), POSTS_ROUTES, ids=[r[0] + r[1][:28] for r in POSTS_ROUTES])
def test_posts_401_is_declared(method, path, spec_path, payload) -> None:
    assert "401" in SPEC["paths"][spec_path][method]["responses"]


# --- 11. GET /conversations/{friendId}/messages (PRO-16) -------------------------------------------

from tests.chat_world import (  # noqa: E402
    A_ID as CHAT_A_ID,
    A_SUB as CHAT_A,
    B_ID as CHAT_B_ID,
    C_ID as CHAT_C_ID,
    D_SUB as CHAT_D,
    make_world as make_chat_world,
)

CHAT_SPEC_PATH = "/conversations/{friendId}/messages"


@pytest.fixture
def chat(build_app):
    world = make_chat_world(build_app)
    with running(world.apps[0]) as client:
        world.client = client
        yield world


def _chat_get(chat, auth_header, friend: str = CHAT_B_ID, sub: str = CHAT_A, query: str = ""):
    url = f"{BASE_PATH}/conversations/{friend}/messages{query}"
    return chat.client.get(url, headers=auth_header(sub)), url


def test_chat_history_200_matches_contract(chat, auth_header) -> None:
    for n in range(3):
        chat.repo.insert_message(CHAT_A_ID if n % 2 == 0 else CHAT_B_ID, CHAT_B_ID if n % 2 == 0 else CHAT_A_ID, f"m{n}", None)
    response, url = _chat_get(chat, auth_header)
    _check_declared(response, "get", CHAT_SPEC_PATH, url, None, 200)
    assert len(response.json()["items"]) == 3 and response.json()["nextCursor"] is None

    # Página parcial: nextCursor es un string (Node: ISO del más antiguo), válido contra MessagePage.
    response, url = _chat_get(chat, auth_header, query="?limit=2")
    _check_declared(response, "get", CHAT_SPEC_PATH, url, None, 200)
    assert isinstance(response.json()["nextCursor"], str)


def test_chat_history_empty_page_matches_contract(chat, auth_header) -> None:
    response, url = _chat_get(chat, auth_header)
    _check_declared(response, "get", CHAT_SPEC_PATH, url, None, 200)


CHAT_ERROR_CASES = [
    ("403-incompleto", CHAT_B_ID, CHAT_D, "", 403),
    ("403-no-amigos", CHAT_C_ID, CHAT_A, "", 403),
    ("404-desconocido", "00000000-0000-4000-8000-000000000000", CHAT_A, "", 404),
]


@pytest.mark.parametrize(("friend", "sub", "query", "status"), [c[1:] for c in CHAT_ERROR_CASES], ids=[c[0] for c in CHAT_ERROR_CASES])
def test_chat_history_declared_errors_match_contract(chat, auth_header, friend, sub, query, status) -> None:
    response, url = _chat_get(chat, auth_header, friend, sub, query)
    _check_declared(response, "get", CHAT_SPEC_PATH, url, None, status)


def test_chat_history_undeclared_errors_use_the_error_schema(chat, auth_header) -> None:
    """400, 401 y 503 no están declarados en listMessages (python-chat.md §9): se validan
    contra el esquema Error común, igual que /users 400 (python-friends.md §10)."""
    for query in ("?limit=0", "?limit=51", "?cursor=no-es-un-cursor"):
        response, _ = _chat_get(chat, auth_header, query=query)
        assert response.status_code == 400
        ERROR_SCHEMA.validate(response.json())
    response = chat.client.get(f"{BASE_PATH}/conversations/{CHAT_B_ID}/messages")
    assert response.status_code == 401
    ERROR_SCHEMA.validate(response.json())
    chat.repo.fail_with = ConnectionError("rds caído")
    response, _ = _chat_get(chat, auth_header)
    assert response.status_code == 503
    ERROR_SCHEMA.validate(response.json())
