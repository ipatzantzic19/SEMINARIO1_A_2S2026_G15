"""POST /bot/messages (PRO-19) con un cliente lexv2-runtime intervenido por Stubber.

Ninguna prueba llama a AWS: firma UNSIGNED + botocore.stub.Stubber; los
errores de red/credenciales se simulan con un doble del cliente.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable, Iterator
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError, NoCredentialsError, ReadTimeoutError
from botocore.stub import Stubber
from fastapi.testclient import TestClient

from app.common.logs import build_handler
from app.config import ConfigError, LexSettings
from app.modules.integrations.lex.client import build_lex_client
from app.modules.integrations.lex.service import EMPTY_RESPONSE_MESSAGE, BotService, lex_session_id
from tests.conftest import COMPLETE_SUB, INCOMPLETE_SUB, assert_error, local_settings, running

URL = "/api/v1/bot/messages"
BOT_ID = "ABCDEFGHIJ"
ALIAS_ID = "KLMNOPQRST"
LEX = LexSettings(region="us-east-1", bot_id=BOT_ID, bot_alias_id=ALIAS_ID, locale_id="es_419")
CLIENT_SESSION = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
AWS_INTERNAL_MESSAGE = "arn:aws:lex:us-east-1:123456789012:bot-alias/ABCDEFGHIJ/KLMNOPQRST (mensaje interno)"

# Vector documentado en docs/api/bot.md para que Node derive el mismo valor.
VECTOR_SUB = "11111111-1111-4111-8111-111111111111"
VECTOR_SESSION = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
VECTOR_LEX_SESSION = "u08f6e4a73d54e8994d037782bb85e5e5052166f55040c985ea3db65ed7fe7f85"


def stubbed_client() -> Any:
    return boto3.client("lexv2-runtime", region_name="us-east-1", config=Config(signature_version=UNSIGNED))


@pytest.fixture
def aws() -> Iterator[tuple[Any, Stubber]]:
    client = stubbed_client()
    with Stubber(client) as stubber:
        yield client, stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def stubber(aws) -> Stubber:
    return aws[1]


@pytest.fixture
def api(build_app, aws) -> Iterator[TestClient]:
    client, _ = aws
    with running(build_app(bot_service=BotService(LEX, lambda: client))) as test_client:
        yield test_client


def expect_turn(
    stubber: Stubber,
    text: str,
    messages: list[dict[str, Any]] | None,
    *,
    sub: str = COMPLETE_SUB,
    session: str = CLIENT_SESSION,
    intent: str = "HorarioAtencion",
    state: str = "Fulfilled",
) -> None:
    response: dict[str, Any] = {
        "sessionId": lex_session_id(sub, session),
        "sessionState": {"intent": {"name": intent, "state": state}, "dialogAction": {"type": "Close"}},
    }
    if messages is not None:
        response["messages"] = messages
    stubber.add_response(
        "recognize_text",
        response,
        {
            "botId": BOT_ID,
            "botAliasId": ALIAS_ID,
            "localeId": "es_419",
            "sessionId": lex_session_id(sub, session),
            "text": text,
        },
    )


def plain(content: str) -> dict[str, str]:
    return {"contentType": "PlainText", "content": content}


class RecordingClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    def recognize_text(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"messages": [plain("Respuesta de prueba")], "sessionId": kwargs["sessionId"]}


def app_with(build_app, client: Any, settings: LexSettings = LEX) -> TestClient:
    return running(build_app(bot_service=BotService(settings, lambda: client)))


# --- 1. sessionId ------------------------------------------------------------


def test_lex_session_id_matches_documented_vector() -> None:
    assert lex_session_id(VECTOR_SUB, VECTOR_SESSION) == VECTOR_LEX_SESSION
    assert lex_session_id(VECTOR_SUB, "sesión ñ #1") == (
        "u56baf61d953cd5e2c81a586de0acea13fd5bb5229270e6d5574dd5fe168ed112"
    )


@pytest.mark.parametrize("session", ["a", "sesión con espacios y ñ", "x" * 100, "../../etc", "{\"json\":1}"])
def test_lex_session_id_always_satisfies_lex_pattern(session: str) -> None:
    import re

    derived = lex_session_id(COMPLETE_SUB, session)
    assert len(derived) == 65
    assert re.fullmatch(r"[0-9a-zA-Z._:-]{2,100}", derived)


def test_lex_session_id_is_bound_to_user() -> None:
    assert lex_session_id(COMPLETE_SUB, CLIENT_SESSION) == lex_session_id(COMPLETE_SUB, CLIENT_SESSION)
    assert lex_session_id(COMPLETE_SUB, CLIENT_SESSION) != lex_session_id(INCOMPLETE_SUB, CLIENT_SESSION)
    assert lex_session_id(COMPLETE_SUB, "a") != lex_session_id(COMPLETE_SUB, "b")


# --- 2. Respuestas ---------------------------------------------------------


def test_replies_with_plain_text_and_returns_client_session_unchanged(api: TestClient, stubber: Stubber, auth_header) -> None:
    expect_turn(stubber, "¿Cuál es el horario de atención?", [plain("Mensaje 1"), plain("Mensaje 2")])
    response = api.post(
        URL, json={"text": "¿Cuál es el horario de atención?", "sessionId": CLIENT_SESSION}, headers=auth_header()
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"messages": ["Mensaje 1", "Mensaje 2"], "sessionId": CLIENT_SESSION}


def test_non_plain_text_messages_are_ignored(api: TestClient, stubber: Stubber, auth_header) -> None:
    expect_turn(
        stubber,
        "hola",
        [
            {"contentType": "SSML", "content": "<speak>hola</speak>"},
            plain("Texto visible"),
            {"contentType": "CustomPayload", "content": "{\"a\":1}"},
            {"contentType": "ImageResponseCard", "imageResponseCard": {"title": "Tarjeta"}},
        ],
    )
    response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert response.json()["messages"] == ["Texto visible"]


@pytest.mark.parametrize("messages", [None, [], [plain("   ")], [{"contentType": "SSML", "content": "<speak/>"}]])
def test_empty_lex_response_returns_neutral_text_and_warns(
    api: TestClient, stubber: Stubber, auth_header, captured_logs, messages
) -> None:
    expect_turn(stubber, "hola", messages)
    response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert response.status_code == 200
    assert response.json() == {"messages": [EMPTY_RESPONSE_MESSAGE], "sessionId": CLIENT_SESSION}
    output = captured_logs()
    assert '"event": "lex.empty_response"' in output and '"level": "WARNING"' in output


def test_fallback_intent_message_is_returned_as_is(api: TestClient, stubber: Stubber, auth_header) -> None:
    expect_turn(stubber, "asdf qwerty", [plain("Mensaje de fallback configurado")], intent="FallbackIntent", state="Fulfilled")
    response = api.post(URL, json={"text": "asdf qwerty", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert response.json() == {"messages": ["Mensaje de fallback configurado"], "sessionId": CLIENT_SESSION}


def test_multi_turn_conversation_uses_same_lex_session(api: TestClient, stubber: Stubber, auth_header) -> None:
    # Turno 1: Lex pide un dato (ElicitSlot); turno 2: el usuario responde y Lex cierra.
    expect_turn(stubber, "quiero información de una carrera", [plain("¿De qué carrera?")], intent="InfoCarrera", state="InProgress")
    expect_turn(stubber, "la primera", [plain("Respuesta para esa carrera")], intent="InfoCarrera", state="Fulfilled")

    first = api.post(URL, json={"text": "quiero información de una carrera", "sessionId": CLIENT_SESSION}, headers=auth_header())
    second = api.post(URL, json={"text": "la primera", "sessionId": first.json()["sessionId"]}, headers=auth_header())

    assert first.json() == {"messages": ["¿De qué carrera?"], "sessionId": CLIENT_SESSION}
    assert second.json() == {"messages": ["Respuesta para esa carrera"], "sessionId": CLIENT_SESSION}


def test_text_is_sent_to_lex_unchanged(api: TestClient, stubber: Stubber, auth_header) -> None:
    text = "  ¿horario   de   biblioteca?  "
    expect_turn(stubber, text, [plain("ok")])  # Stubber exige el texto idéntico
    assert api.post(URL, json={"text": text, "sessionId": CLIENT_SESSION}, headers=auth_header()).status_code == 200


def test_client_session_with_symbols_is_derived_not_forwarded(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "hola", "sessionId": "ñ"}, headers=auth_header())
    assert response.json()["sessionId"] == "ñ"
    assert client.calls[0]["sessionId"] == lex_session_id(COMPLETE_SUB, "ñ")
    assert client.calls[0]["botId"] == BOT_ID and client.calls[0]["localeId"] == "es_419"


# --- 3. Validación (400) sin llamar a Lex -----------------------------------

INVALID = {
    "texto vacío": {"text": "", "sessionId": CLIENT_SESSION},
    "solo espacios": {"text": " \n\t ", "sessionId": CLIENT_SESSION},
    "más de 500": {"text": "a" * 501, "sessionId": CLIENT_SESSION},
    "sin texto": {"sessionId": CLIENT_SESSION},
    "sin sessionId": {"text": "hola"},
    "sessionId vacío": {"text": "hola", "sessionId": ""},
    "sessionId de 101": {"text": "hola", "sessionId": "s" * 101},
    "sessionId no string": {"text": "hola", "sessionId": 123},
}


@pytest.mark.parametrize("payload", INVALID.values(), ids=INVALID.keys())
def test_invalid_payload_returns_400_without_calling_lex(build_app, auth_header, payload: dict) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json=payload, headers=auth_header())
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert body["details"]["fields"]
    assert client.calls == []


def test_limits_accept_500_chars_and_1_char_session(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "a" * 500, "sessionId": "s"}, headers=auth_header())
    assert response.status_code == 200
    assert len(client.calls) == 1


# --- 4. Errores de AWS y configuración -------------------------------------

AWS_ERRORS = [
    ("ThrottlingException", 429, 429, "RATE_LIMITED"),
    ("ConflictException", 409, 429, "RATE_LIMITED"),
    ("AccessDeniedException", 403, 503, "SERVICE_UNAVAILABLE"),
    ("ResourceNotFoundException", 404, 503, "SERVICE_UNAVAILABLE"),
    ("ValidationException", 400, 503, "SERVICE_UNAVAILABLE"),
    ("DependencyFailedException", 424, 503, "SERVICE_UNAVAILABLE"),
    ("BadGatewayException", 502, 503, "SERVICE_UNAVAILABLE"),
    ("InternalServerException", 500, 503, "SERVICE_UNAVAILABLE"),
    ("ExpiredTokenException", 400, 503, "SERVICE_UNAVAILABLE"),
]


@pytest.mark.parametrize(("aws_code", "aws_status", "status", "code"), AWS_ERRORS, ids=[e[0] for e in AWS_ERRORS])
def test_aws_errors_are_mapped_and_logged_without_internal_message(
    api: TestClient, aws, auth_header, captured_logs, aws_code: str, aws_status: int, status: int, code: str
) -> None:
    client, stubber = aws
    stubber.add_client_error(
        "recognize_text", service_error_code=aws_code, service_message=AWS_INTERNAL_MESSAGE, http_status_code=aws_status
    )
    text = "Pregunta privada de Ana"
    response = api.post(URL, json={"text": text, "sessionId": CLIENT_SESSION}, headers=auth_header())

    body = assert_error(response, status, code)
    assert body["details"] is None
    assert "arn:aws" not in response.text and aws_code not in response.text

    output = captured_logs()
    assert f'"awsErrorCode": "{aws_code}"' in output
    assert f'"errorType": "{client.exceptions.from_code(aws_code).__name__}"' in output
    for forbidden in (text, AWS_INTERNAL_MESSAGE, "arn:aws", CLIENT_SESSION, lex_session_id(COMPLETE_SUB, CLIENT_SESSION)):
        assert forbidden not in output


@pytest.mark.parametrize(
    "error",
    [
        NoCredentialsError(),
        EndpointConnectionError(endpoint_url="https://runtime-v2-lex.us-east-1.amazonaws.com"),
        ReadTimeoutError(endpoint_url="https://runtime-v2-lex.us-east-1.amazonaws.com"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_network_and_credential_failures_return_503(build_app, auth_header, error: Exception) -> None:
    with app_with(build_app, RecordingClient(error)) as api:
        response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert "amazonaws" not in response.text


def test_unconfigured_bot_returns_503_without_creating_client(build_app, auth_header, captured_logs) -> None:
    created: list[Any] = []
    service = BotService(LexSettings(region="us-east-1"), lambda: created.append(1))
    with running(build_app(bot_service=service)) as api:
        response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert created == []
    assert '"event": "lex.not_configured"' in captured_logs()


def test_default_app_without_lex_variables_returns_503(client: TestClient, auth_header) -> None:
    response = client.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert_error(response, 503, "SERVICE_UNAVAILABLE")


def test_mapped_error_carries_aws_code_for_smoke_script(aws) -> None:
    client, stubber = aws
    stubber.add_client_error("recognize_text", service_error_code="ThrottlingException", http_status_code=429)
    with pytest.raises(Exception) as info:
        BotService(LEX, lambda: client).send(COMPLETE_SUB, CLIENT_SESSION, "hola")
    assert info.value.status_code == 429
    assert info.value.aws_error_code == "ThrottlingException"


# --- 5. Autenticación y perfil (el proxy no se usa) -------------------------


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer no-es-un-jwt"}], ids=["sin token", "token inválido"])
def test_unauthenticated_returns_401_without_calling_lex(build_app, headers: dict) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=headers)
    assert_error(response, 401, "UNAUTHENTICATED")
    assert client.calls == []


def test_expired_token_returns_401_without_calling_lex(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header(exp=1))
    assert_error(response, 401, "UNAUTHENTICATED")
    assert client.calls == []


def test_401_takes_precedence_over_invalid_body(build_app) -> None:
    with app_with(build_app, RecordingClient()) as api:
        assert_error(api.post(URL, json={"text": ""}), 401, "UNAUTHENTICATED")


def test_403_takes_precedence_over_invalid_body(build_app, auth_header) -> None:
    with app_with(build_app, RecordingClient()) as api:
        response = api.post(URL, json={"text": ""}, headers=auth_header(INCOMPLETE_SUB))
    assert_error(response, 403, "FORBIDDEN")


def test_incomplete_profile_returns_403_without_calling_lex(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header(INCOMPLETE_SUB))
    body = assert_error(response, 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}
    assert client.calls == []


# --- 6. Logs -------------------------------------------------------------------


@pytest.fixture
def captured_logs() -> Iterator[Callable[[], str]]:
    stream = io.StringIO()
    handler = build_handler(stream)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield stream.getvalue
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def test_success_log_has_intent_but_no_text_reply_session_or_token(
    api: TestClient, stubber: Stubber, make_token, captured_logs
) -> None:
    text = "Consulta confidencial de Ana"
    reply = "Respuesta confidencial del bot"
    expect_turn(stubber, text, [plain(reply)])
    token = make_token()
    api.post(URL, json={"text": text, "sessionId": CLIENT_SESSION}, headers={"Authorization": f"Bearer {token}"})

    output = captured_logs()
    assert '"event": "lex.replied"' in output
    assert '"intentName": "HorarioAtencion"' in output and '"messageCount": 1' in output
    for forbidden in (text, reply, "confidencial", token, CLIENT_SESSION, lex_session_id(COMPLETE_SUB, CLIENT_SESSION)):
        assert forbidden not in output


# --- 7. Cliente y configuración ---------------------------------------------


@pytest.fixture
def isolated_aws_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    for name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


def test_build_lex_client_uses_runtime_region_and_timeouts(isolated_aws_config) -> None:
    client = build_lex_client(LexSettings(region="us-east-1", timeout_seconds=4))
    assert client.meta.service_model.service_name == "lexv2-runtime"
    assert client.meta.region_name == "us-east-1"
    assert client.meta.config.connect_timeout == 4 and client.meta.config.read_timeout == 4
    assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 2}


def test_client_is_created_lazily_and_once(build_app, auth_header) -> None:
    created: list[RecordingClient] = []

    def factory() -> RecordingClient:
        created.append(RecordingClient())
        return created[-1]

    with running(build_app(bot_service=BotService(LEX, factory))) as api:
        assert created == []
        for _ in range(3):
            api.post(URL, json={"text": "hola", "sessionId": CLIENT_SESSION}, headers=auth_header())
    assert len(created) == 1 and len(created[0].calls) == 3


def test_lex_settings_defaults() -> None:
    settings = local_settings(AWS_REGION="us-west-2").lex
    assert settings == LexSettings(region="us-west-2", bot_id=None, bot_alias_id=None, locale_id="es_419", timeout_seconds=5)
    assert not settings.configured


def test_lex_settings_configured() -> None:
    settings = local_settings(LEX_BOT_ID=BOT_ID, LEX_BOT_ALIAS_ID=ALIAS_ID, LEX_TIMEOUT_SECONDS="8").lex
    assert settings.configured and settings.timeout_seconds == 8 and settings.region == "us-east-1"


@pytest.mark.parametrize(
    ("env", "fragment"),
    [
        ({"LEX_BOT_ID": BOT_ID}, "deben definirse juntas"),
        ({"LEX_BOT_ALIAS_ID": ALIAS_ID}, "deben definirse juntas"),
        ({"LEX_BOT_ID": "corto", "LEX_BOT_ALIAS_ID": ALIAS_ID}, "LEX_BOT_ID"),
        ({"LEX_BOT_ID": BOT_ID, "LEX_BOT_ALIAS_ID": "alias/prod!"}, "LEX_BOT_ALIAS_ID"),
        ({"LEX_LOCALE_ID": "es-419"}, "LEX_LOCALE_ID"),
        ({"LEX_REGION": "Virginia"}, "LEX_REGION"),
        ({"LEX_TIMEOUT_SECONDS": "0"}, "LEX_TIMEOUT_SECONDS"),
    ],
)
def test_invalid_lex_settings_are_rejected(env: dict, fragment: str) -> None:
    with pytest.raises(ConfigError) as info:
        local_settings(**env)
    assert fragment in str(info.value)


def test_test_alias_is_rejected_in_production_but_allowed_locally() -> None:
    from app.config import Settings

    assert local_settings(LEX_BOT_ID=BOT_ID, LEX_BOT_ALIAS_ID="TSTALIASID").lex.configured
    production = {
        "APP_ENV": "production",
        "AWS_REGION": "us-east-1",
        "COGNITO_USER_POOL_ID": "us-east-1_testPool",
        "COGNITO_APP_CLIENT_ID": "client",
        "RDS_HOST": "db",
        "RDS_USER": "u",
        "RDS_PASSWORD": "p",
        "S3_IMAGES_BUCKET": "bucket",
        "LEX_BOT_ID": BOT_ID,
        "LEX_BOT_ALIAS_ID": "TSTALIASID",
    }
    with pytest.raises(ConfigError) as info:
        Settings.from_env(production)
    assert "alias de prueba" in str(info.value)
    production.pop("LEX_BOT_ID")
    production.pop("LEX_BOT_ALIAS_ID")
    assert not Settings.from_env(production).lex.configured  # opcional en production
