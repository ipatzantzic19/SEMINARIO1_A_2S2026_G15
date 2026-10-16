"""POST /translations (PRO-18) con un cliente boto3 real intervenido por Stubber.

Ninguna prueba llama a AWS: el cliente usa firma UNSIGNED (no necesita
credenciales) y botocore.stub.Stubber responde en lugar del servicio. Los
errores de red/credenciales se simulan con un doble del cliente.
"""

from __future__ import annotations

import copy
import io
import logging
from collections.abc import Callable, Iterator
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import (
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)
from botocore.stub import Stubber
from fastapi.testclient import TestClient

from app.common.logs import build_handler
from app.config import TranslateSettings
from app.modules.integrations.translate.client import build_translate_client
from app.modules.integrations.translate.router import TranslateRequest
from app.modules.integrations.translate.service import SUPPORTED_TARGETS, TranslationService
from tests.conftest import INCOMPLETE_SUB, assert_error, local_settings, running

URL = "/api/v1/translations"
AWS_INTERNAL_MESSAGE = "arn:aws:iam::123456789012:role/internal no autorizado (mensaje interno)"


def stubbed_client() -> Any:
    return boto3.client("translate", region_name="us-east-1", config=Config(signature_version=UNSIGNED))


@pytest.fixture
def aws() -> Iterator[tuple[Any, Stubber]]:
    client = stubbed_client()
    with Stubber(client) as stubber:
        yield client, stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def api(build_app, aws) -> Iterator[TestClient]:
    client, _ = aws
    with running(build_app(translation_service=TranslationService(lambda: client))) as test_client:
        yield test_client


@pytest.fixture
def stubber(aws) -> Stubber:
    return aws[1]


def expect_translation(
    stubber: Stubber, text: str, target: str, *, source: str = "auto", detected: str = "es", translated: str | None = None
) -> str:
    translated = translated if translated is not None else f"<{target}> traducción"
    stubber.add_response(
        "translate_text",
        {"TranslatedText": translated, "SourceLanguageCode": detected, "TargetLanguageCode": target},
        {"Text": text, "SourceLanguageCode": source, "TargetLanguageCode": target},
    )
    return translated


class RecordingClient:
    """Doble del cliente: registra llamadas y opcionalmente lanza un error."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    def translate_text(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"TranslatedText": "Hello", "SourceLanguageCode": "es", "TargetLanguageCode": kwargs["TargetLanguageCode"]}


def app_with(build_app, client: Any) -> TestClient:
    return running(build_app(translation_service=TranslationService(lambda: client)))


# --- 1. Cuatro destinos -----------------------------------------------------


def test_contract_targets_are_exactly_four_including_spanish() -> None:
    assert SUPPORTED_TARGETS == ("es", "en", "fr", "de")
    assert set(TranslateRequest.model_fields["targetLanguage"].annotation.__args__) == set(SUPPORTED_TARGETS)


@pytest.mark.parametrize("target", SUPPORTED_TARGETS)
def test_translates_to_each_supported_target(api: TestClient, stubber: Stubber, auth_header, target: str) -> None:
    text = "Hola, bienvenidos a Semi-Social." if target != "es" else "Hello, welcome to Semi-Social."
    detected = "es" if target != "es" else "en"
    translated = expect_translation(stubber, text, target, detected=detected)

    response = api.post(URL, json={"text": text, "targetLanguage": target}, headers=auth_header())

    assert response.status_code == 200, response.text
    assert response.json() == {"translatedText": translated, "sourceLanguage": detected, "targetLanguage": target}


def test_explicit_source_language_is_forwarded(api: TestClient, stubber: Stubber, auth_header) -> None:
    expect_translation(stubber, "Good morning", "fr", source="en", detected="en", translated="Bonjour")
    response = api.post(
        URL, json={"text": "Good morning", "sourceLanguage": "en", "targetLanguage": "fr"}, headers=auth_header()
    )
    assert response.status_code == 200
    assert response.json() == {"translatedText": "Bonjour", "sourceLanguage": "en", "targetLanguage": "fr"}


def test_regional_source_code_is_accepted(api: TestClient, stubber: Stubber, auth_header) -> None:
    expect_translation(stubber, "你好", "es", source="zh-TW", detected="zh-TW", translated="Hola")
    response = api.post(URL, json={"text": "你好", "sourceLanguage": "zh-TW", "targetLanguage": "es"}, headers=auth_header())
    assert response.status_code == 200


# --- 2. El texto original queda intacto -----------------------------------


def test_original_text_is_sent_unchanged_and_not_altered(api: TestClient, stubber: Stubber, auth_header) -> None:
    original = "  Hola   mundo,\n¿cómo están? 😀  "
    payload = {"text": original, "targetLanguage": "en"}
    snapshot = copy.deepcopy(payload)
    # Stubber exige que Text llegue idéntico (sin recortar espacios ni normalizar).
    expect_translation(stubber, original, "en", translated="Hello world, how are you? 😀")

    response = api.post(URL, json=payload, headers=auth_header())

    assert response.status_code == 200
    assert payload == snapshot
    assert response.json()["translatedText"] != original


def test_translation_does_not_use_the_database(build_app, auth_header) -> None:
    class NoQueriesDatabase:
        configured = True

        def open(self, *, required: bool) -> None: ...
        def close(self) -> None: ...
        def ping(self) -> bool:
            return True

        def __getattr__(self, name: str) -> Any:  # cualquier otra operación (connection, execute...)
            raise AssertionError(f"La traducción no debe usar la BD ({name})")

    client = RecordingClient()
    app = build_app(NoQueriesDatabase(), translation_service=TranslationService(lambda: client))
    with running(app) as api:
        response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header())
    assert response.status_code == 200
    assert len(client.calls) == 1


def test_explicit_source_equal_to_target_returns_text_without_calling_aws(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(
            URL, json={"text": "Hola amigos", "sourceLanguage": "es", "targetLanguage": "es"}, headers=auth_header()
        )
    assert response.status_code == 200
    assert response.json() == {"translatedText": "Hola amigos", "sourceLanguage": "es", "targetLanguage": "es"}
    assert client.calls == []


def test_auto_detected_language_equal_to_target_returns_aws_result(api: TestClient, stubber: Stubber, auth_header) -> None:
    expect_translation(stubber, "Hola amigos", "es", detected="es", translated="Hola amigos")
    response = api.post(URL, json={"text": "Hola amigos", "targetLanguage": "es"}, headers=auth_header())
    assert response.json() == {"translatedText": "Hola amigos", "sourceLanguage": "es", "targetLanguage": "es"}


@pytest.mark.parametrize("aws_code", ["UnsupportedLanguagePairException"])
def test_auto_detected_equal_to_target_rejected_by_aws_returns_original(
    api: TestClient, stubber: Stubber, auth_header, aws_code: str
) -> None:
    stubber.add_client_error(
        "translate_text",
        service_error_code=aws_code,
        service_message=AWS_INTERNAL_MESSAGE,
        http_status_code=400,
        modeled_fields={"SourceLanguageCode": "es", "TargetLanguageCode": "es"},
    )
    response = api.post(URL, json={"text": "Hola amigos", "targetLanguage": "es"}, headers=auth_header())
    assert response.status_code == 200
    assert response.json() == {"translatedText": "Hola amigos", "sourceLanguage": "es", "targetLanguage": "es"}


# --- 3. Validación (400) sin llamar a AWS ---------------------------------

INVALID_PAYLOADS = {
    "texto vacío": {"text": "", "targetLanguage": "en"},
    "solo espacios": {"text": "  \n\t ", "targetLanguage": "en"},
    "sin texto": {"targetLanguage": "en"},
    "texto null": {"text": None, "targetLanguage": "en"},
    "más de 5000 caracteres": {"text": "a" * 5001, "targetLanguage": "en"},
    "más de 10000 bytes UTF-8": {"text": "😀" * 2501, "targetLanguage": "en"},
    "idioma no soportado it": {"text": "Hola", "targetLanguage": "it"},
    "idioma no soportado pt": {"text": "Hola", "targetLanguage": "pt"},
    "idioma en mayúsculas": {"text": "Hola", "targetLanguage": "EN"},
    "sin idioma destino": {"text": "Hola"},
    "destino auto": {"text": "Hola", "targetLanguage": "auto"},
    "origen inválido": {"text": "Hola", "sourceLanguage": "spanish", "targetLanguage": "en"},
    "origen vacío": {"text": "Hola", "sourceLanguage": "", "targetLanguage": "en"},
    "origen en mayúsculas": {"text": "Hola", "sourceLanguage": "ES", "targetLanguage": "en"},
}


@pytest.mark.parametrize("payload", INVALID_PAYLOADS.values(), ids=INVALID_PAYLOADS.keys())
def test_invalid_payload_returns_400_without_calling_aws(build_app, auth_header, payload: dict) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json=payload, headers=auth_header())
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert body["details"]["fields"], body
    assert client.calls == []


def test_400_details_do_not_echo_the_text(build_app, auth_header) -> None:
    secret_text = "texto privado " * 400  # > 5000 caracteres
    with app_with(build_app, RecordingClient()) as api:
        response = api.post(URL, json={"text": secret_text, "targetLanguage": "en"}, headers=auth_header())
    assert response.status_code == 400
    assert "texto privado" not in response.text


def test_limits_accept_exactly_5000_chars_and_10000_bytes(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        ascii_max = api.post(URL, json={"text": "a" * 5000, "targetLanguage": "en"}, headers=auth_header())
        bytes_max = api.post(URL, json={"text": "😀" * 2500, "targetLanguage": "en"}, headers=auth_header())
    assert ascii_max.status_code == 200
    assert bytes_max.status_code == 200
    assert len(client.calls) == 2


def test_byte_limit_error_names_the_field(build_app, auth_header) -> None:
    with app_with(build_app, RecordingClient()) as api:
        response = api.post(URL, json={"text": "ñ" * 5000, "targetLanguage": "en"}, headers=auth_header())
    assert response.status_code == 200  # 10000 bytes exactos
    with app_with(build_app, RecordingClient()) as api:
        response = api.post(URL, json={"text": "€" * 3334, "targetLanguage": "en"}, headers=auth_header())
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert body["details"]["fields"][0]["field"] == "text"
    assert "10000 bytes" in body["details"]["fields"][0]["error"]


# --- 4. Errores de AWS ------------------------------------------------------

AWS_ERRORS = [
    ("ThrottlingException", 400, 429, "RATE_LIMITED", None),
    ("TooManyRequestsException", 400, 429, "RATE_LIMITED", None),
    ("LimitExceededException", 400, 429, "RATE_LIMITED", None),
    ("ServiceUnavailableException", 500, 503, "SERVICE_UNAVAILABLE", None),
    ("InternalServerException", 500, 503, "SERVICE_UNAVAILABLE", None),
    ("AccessDeniedException", 400, 503, "SERVICE_UNAVAILABLE", None),
    ("UnrecognizedClientException", 400, 503, "SERVICE_UNAVAILABLE", None),
    ("ExpiredTokenException", 400, 503, "SERVICE_UNAVAILABLE", None),
    ("DetectedLanguageLowConfidenceException", 400, 400, "VALIDATION_ERROR", "LANGUAGE_DETECTION_LOW_CONFIDENCE"),
    ("UnsupportedLanguagePairException", 400, 400, "VALIDATION_ERROR", "UNSUPPORTED_LANGUAGE_PAIR"),
    ("TextSizeLimitExceededException", 400, 400, "VALIDATION_ERROR", "TEXT_TOO_LARGE"),
    ("InvalidRequestException", 400, 400, "VALIDATION_ERROR", "INVALID_TRANSLATION_REQUEST"),
]


@pytest.mark.parametrize(
    ("aws_code", "aws_status", "status", "code", "reason"), AWS_ERRORS, ids=[e[0] for e in AWS_ERRORS]
)
def test_aws_errors_are_mapped_without_internal_message(
    api: TestClient, stubber: Stubber, auth_header, aws_code: str, aws_status: int, status: int, code: str, reason: str | None
) -> None:
    stubber.add_client_error(
        "translate_text", service_error_code=aws_code, service_message=AWS_INTERNAL_MESSAGE, http_status_code=aws_status
    )
    response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header())

    body = assert_error(response, status, code)
    assert "arn:aws" not in response.text and aws_code not in response.text
    if reason:
        assert body["details"] == {"reason": reason}
    else:
        assert body["details"] is None


def test_unsupported_pair_with_auto_and_different_detected_language_is_400(
    api: TestClient, stubber: Stubber, auth_header
) -> None:
    stubber.add_client_error(
        "translate_text",
        service_error_code="UnsupportedLanguagePairException",
        service_message=AWS_INTERNAL_MESSAGE,
        http_status_code=400,
        modeled_fields={"SourceLanguageCode": "xx", "TargetLanguageCode": "en"},
    )
    response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header())
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "UNSUPPORTED_LANGUAGE_PAIR"}


@pytest.mark.parametrize(
    "error",
    [
        NoCredentialsError(),
        EndpointConnectionError(endpoint_url="https://translate.us-east-1.amazonaws.com"),
        ConnectTimeoutError(endpoint_url="https://translate.us-east-1.amazonaws.com"),
        ReadTimeoutError(endpoint_url="https://translate.us-east-1.amazonaws.com"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_network_and_credential_failures_return_503(build_app, auth_header, error: Exception) -> None:
    with app_with(build_app, RecordingClient(error)) as api:
        response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header())
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert "amazonaws" not in response.text


# --- 5. Autenticación y perfil -----------------------------------------------


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer no-es-un-jwt"}], ids=["sin token", "token inválido"])
def test_unauthenticated_returns_401_without_calling_aws(build_app, headers: dict) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=headers)
    assert_error(response, 401, "UNAUTHENTICATED")
    assert client.calls == []


def test_expired_token_returns_401(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header(exp=1))
    assert_error(response, 401, "UNAUTHENTICATED")
    assert client.calls == []


def test_401_takes_precedence_over_invalid_body(build_app) -> None:
    with app_with(build_app, RecordingClient()) as api:
        response = api.post(URL, json={"text": "", "targetLanguage": "it"})
    assert_error(response, 401, "UNAUTHENTICATED")


def test_incomplete_profile_returns_403_without_calling_aws(build_app, auth_header) -> None:
    client = RecordingClient()
    with app_with(build_app, client) as api:
        response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header(INCOMPLETE_SUB))
    body = assert_error(response, 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}
    assert client.calls == []


# --- 6. Logs sin texto ni tokens -------------------------------------------


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


def test_logs_do_not_contain_text_translation_or_token(
    api: TestClient, stubber: Stubber, make_token, captured_logs
) -> None:
    text = "Mensaje confidencial de Ana para su familia"
    translated = expect_translation(stubber, text, "de", translated="Vertrauliche Nachricht von Ana an ihre Familie")
    token = make_token()
    response = api.post(URL, json={"text": text, "targetLanguage": "de"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    output = captured_logs()
    assert '"event": "translate.translated"' in output
    assert '"targetLanguage": "de"' in output and f'"chars": {len(text)}' in output
    for forbidden in (text, translated, "confidencial", "Vertrauliche", token):
        assert forbidden not in output


@pytest.mark.parametrize(
    ("aws_code", "aws_status", "status"),
    [
        ("AccessDeniedException", 400, 503),
        ("ServiceUnavailableException", 500, 503),
        ("ThrottlingException", 400, 429),
        ("TooManyRequestsException", 400, 429),
        ("DetectedLanguageLowConfidenceException", 400, 400),
        ("UnsupportedLanguagePairException", 400, 400),
    ],
)
def test_aws_error_log_has_code_and_exception_but_not_message_or_text(
    api: TestClient, aws, auth_header, captured_logs, aws_code: str, aws_status: int, status: int
) -> None:
    client, stubber = aws
    text = "Texto privado de Ana para traducir"
    stubber.add_client_error(
        "translate_text", service_error_code=aws_code, service_message=AWS_INTERNAL_MESSAGE, http_status_code=aws_status
    )
    response = api.post(URL, json={"text": text, "targetLanguage": "en"}, headers=auth_header())
    assert response.status_code == status

    output = captured_logs()
    exception_name = client.exceptions.from_code(aws_code).__name__
    assert '"event": "translate.aws_error"' in output
    assert f'"awsErrorCode": "{aws_code}"' in output
    assert f'"errorType": "{exception_name}"' in output
    for forbidden in (text, "Texto privado", AWS_INTERNAL_MESSAGE, "arn:aws", "mensaje interno"):
        assert forbidden not in output


def test_mapped_error_carries_aws_code_for_diagnostics_but_not_in_response(api: TestClient, aws, auth_header) -> None:
    client, stubber = aws
    stubber.add_client_error(
        "translate_text", service_error_code="AccessDeniedException", service_message=AWS_INTERNAL_MESSAGE, http_status_code=400
    )
    service = TranslationService(lambda: client)
    with pytest.raises(Exception) as info:
        service.translate("Hola", "auto", "en")
    assert info.value.aws_error_code == "AccessDeniedException"
    assert info.value.status_code == 503

    stubber.add_client_error("translate_text", service_error_code="AccessDeniedException", http_status_code=400)
    response = api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header())
    assert "AccessDenied" not in response.text


def test_smoke_script_fail_line_shows_aws_code() -> None:
    import importlib.util
    from pathlib import Path

    from app.common.errors import ApiError, ServiceUnavailableError
    from app.modules.integrations.translate.service import _with_aws_cause

    path = Path(__file__).resolve().parents[1] / "scripts" / "translate_smoke.py"
    spec = importlib.util.spec_from_file_location("translate_smoke", path)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)

    throttled = _with_aws_cause(ApiError(429, "RATE_LIMITED"), "ThrottlingException", "ThrottlingException")
    assert smoke.describe_error(throttled) == "HTTP 429 RATE_LIMITED AWS=ThrottlingException"
    offline = _with_aws_cause(ServiceUnavailableError(), None, "EndpointConnectionError")
    assert smoke.describe_error(offline) == "HTTP 503 SERVICE_UNAVAILABLE boto=EndpointConnectionError"
    assert smoke.describe_error(ApiError(400, "VALIDATION_ERROR")) == "HTTP 400 VALIDATION_ERROR"


# --- 7. Cliente boto3 y configuración ---------------------------------------


def test_client_is_created_lazily_and_once(build_app, auth_header) -> None:
    created: list[Any] = []

    def factory() -> Any:
        created.append(RecordingClient())
        return created[-1]

    with running(build_app(translation_service=TranslationService(factory))) as api:
        assert created == []
        for _ in range(3):
            api.post(URL, json={"text": "Hola", "targetLanguage": "en"}, headers=auth_header())
    assert len(created) == 1
    assert len(created[0].calls) == 3


@pytest.fixture
def isolated_aws_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Aísla la cadena de credenciales de ~/.aws, AWS_* y del IMDS del equipo."""
    for name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


def test_build_translate_client_uses_region_timeouts_and_default_credentials(isolated_aws_config) -> None:
    client = build_translate_client(TranslateSettings(region="us-east-1", timeout_seconds=4))
    assert client.meta.region_name == "us-east-1"
    assert client.meta.config.connect_timeout == 4
    assert client.meta.config.read_timeout == 4
    assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 2}
    assert client.meta.service_model.service_name == "translate"


def test_translate_settings_default_to_aws_region() -> None:
    settings = local_settings(AWS_REGION="us-west-2")
    assert settings.translate.region == "us-west-2"
    assert settings.translate.timeout_seconds == 5


def test_translate_settings_overrides() -> None:
    settings = local_settings(TRANSLATE_REGION="eu-west-1", TRANSLATE_TIMEOUT_SECONDS="10")
    assert settings.translate.region == "eu-west-1"
    assert settings.translate.timeout_seconds == 10


@pytest.mark.parametrize(
    ("env", "fragment"),
    [
        ({"TRANSLATE_REGION": "Virginia"}, "TRANSLATE_REGION"),
        ({"TRANSLATE_TIMEOUT_SECONDS": "0"}, "TRANSLATE_TIMEOUT_SECONDS"),
        ({"TRANSLATE_TIMEOUT_SECONDS": "abc"}, "TRANSLATE_TIMEOUT_SECONDS"),
    ],
)
def test_invalid_translate_settings_are_rejected_without_values(env: dict, fragment: str) -> None:
    from app.config import ConfigError

    with pytest.raises(ConfigError) as info:
        local_settings(**env)
    assert fragment in str(info.value)
    assert all(value not in str(info.value) for value in env.values() if len(value) > 3)
