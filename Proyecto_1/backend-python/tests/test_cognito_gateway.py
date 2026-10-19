"""CognitoGateway con un cliente boto3 real intervenido por Stubber.

Ninguna prueba llama a AWS: el cliente no firma (UNSIGNED) y Stubber responde
en lugar de Cognito. Los errores de red se simulan con un doble del cliente.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError, ReadTimeoutError
from botocore.stub import Stubber

from app.common.errors import ApiError
from app.common.logs import build_handler
from app.modules.integrations.cognito.gateway import AuthChallenge, AuthTokens, CognitoGateway

CLIENT_ID = "test-client-id"
EMAIL = "ana@example.com"
PASSWORD = "ClaveSegura123!"
DPI = "1234567890123"
AWS_INTERNAL_MESSAGE = "arn:aws:cognito-idp:us-east-1:123456789012:userpool/interno mensaje de AWS"


@pytest.fixture
def stubbed() -> Iterator[tuple[CognitoGateway, Stubber]]:
    client = boto3.client("cognito-idp", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    with Stubber(client) as stubber:
        yield CognitoGateway(CLIENT_ID, lambda: client), stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
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


def _error(stubber: Stubber, method: str, code: str) -> None:
    stubber.add_client_error(method, service_error_code=code, service_message=AWS_INTERNAL_MESSAGE, http_status_code=400)


# --- llamadas exitosas -----------------------------------------------------


def test_sign_up_sends_attributes_and_returns_sub(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "sign_up",
        {"UserConfirmed": False, "UserSub": "sub-123"},
        {
            "ClientId": CLIENT_ID,
            "Username": EMAIL,
            "Password": PASSWORD,
            "UserAttributes": [
                {"Name": "email", "Value": EMAIL},
                {"Name": "name", "Value": "Ana Prueba"},
                {"Name": "custom:dpi", "Value": DPI},
            ],
        },
    )
    result = gateway.sign_up(EMAIL, PASSWORD, "Ana Prueba", DPI)
    assert result.sub == "sub-123" and result.confirmed is False


def test_confirm_sign_up(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "confirm_sign_up", {}, {"ClientId": CLIENT_ID, "Username": EMAIL, "ConfirmationCode": "123456"}
    )
    gateway.confirm_sign_up(EMAIL, "123456")


def test_password_auth_returns_tokens(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "initiate_auth",
        {
            "AuthenticationResult": {
                "AccessToken": "access",
                "IdToken": "id",
                "RefreshToken": "refresh",
                "ExpiresIn": 3600,
                "TokenType": "Bearer",
            }
        },
        {
            "ClientId": CLIENT_ID,
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {"USERNAME": EMAIL, "PASSWORD": PASSWORD},
        },
    )
    assert gateway.password_auth(EMAIL, PASSWORD) == AuthTokens("access", "id", "refresh", 3600)


def test_password_auth_returns_challenge(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "initiate_auth",
        {
            "ChallengeName": "NEW_PASSWORD_REQUIRED",
            "Session": "s" * 40,
            "ChallengeParameters": {"requiredAttributes": "[]"},
        },
    )
    outcome = gateway.password_auth(EMAIL, PASSWORD)
    assert outcome == AuthChallenge("NEW_PASSWORD_REQUIRED", "s" * 40, {"requiredAttributes": "[]"})


def test_incomplete_authentication_result_is_503(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response("initiate_auth", {"AuthenticationResult": {"AccessToken": "a", "ExpiresIn": 3600}})
    with pytest.raises(ApiError) as info:
        gateway.password_auth(EMAIL, PASSWORD)
    assert info.value.status_code == 503


def test_update_attributes_only_sends_changes(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "update_user_attributes",
        {},
        {"AccessToken": "token", "UserAttributes": [{"Name": "custom:dpi", "Value": DPI}]},
    )
    gateway.update_attributes("token", dpi=DPI)
    # Sin cambios no hay llamada (Stubber fallaría con una llamada inesperada).
    gateway.update_attributes("token")


def test_get_user_attributes(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "get_user",
        {
            "Username": "sub-123",
            "UserAttributes": [
                {"Name": "sub", "Value": "sub-123"},
                {"Name": "email", "Value": EMAIL},
                {"Name": "name", "Value": "Ana"},
                {"Name": "custom:dpi", "Value": DPI},
            ],
        },
        {"AccessToken": "token"},
    )
    assert gateway.get_user_attributes("token") == {"sub": "sub-123", "email": EMAIL, "name": "Ana", "custom:dpi": DPI}


# --- mapeo de errores ------------------------------------------------------

ERROR_CASES = [
    # (método del gateway, método boto3, código AWS, estado, code, reason)
    ("sign_up", "sign_up", "UsernameExistsException", 409, "CONFLICT", "EMAIL_TAKEN"),
    ("sign_up", "sign_up", "InvalidPasswordException", 400, "VALIDATION_ERROR", "PASSWORD_POLICY"),
    ("sign_up", "sign_up", "InvalidParameterException", 400, "VALIDATION_ERROR", "INVALID_PARAMETER"),
    ("sign_up", "sign_up", "LimitExceededException", 429, "RATE_LIMITED", None),
    ("sign_up", "sign_up", "TooManyRequestsException", 429, "RATE_LIMITED", None),
    ("sign_up", "sign_up", "CodeDeliveryFailureException", 503, "SERVICE_UNAVAILABLE", None),
    ("sign_up", "sign_up", "InternalErrorException", 503, "SERVICE_UNAVAILABLE", None),
    ("sign_up", "sign_up", "ResourceNotFoundException", 503, "SERVICE_UNAVAILABLE", None),
    ("confirm", "confirm_sign_up", "CodeMismatchException", 400, "VALIDATION_ERROR", "CODE_MISMATCH"),
    ("confirm", "confirm_sign_up", "ExpiredCodeException", 400, "VALIDATION_ERROR", "CODE_EXPIRED"),
    ("confirm", "confirm_sign_up", "UserNotFoundException", 404, "NOT_FOUND", None),
    ("confirm", "confirm_sign_up", "NotAuthorizedException", 400, "VALIDATION_ERROR", "CONFIRMATION_NOT_ALLOWED"),
    ("confirm", "confirm_sign_up", "TooManyFailedAttemptsException", 429, "RATE_LIMITED", None),
    ("confirm", "confirm_sign_up", "LimitExceededException", 429, "RATE_LIMITED", None),
    ("login", "initiate_auth", "NotAuthorizedException", 401, "UNAUTHENTICATED", None),
    ("login", "initiate_auth", "UserNotFoundException", 401, "UNAUTHENTICATED", None),
    ("login", "initiate_auth", "UserNotConfirmedException", 401, "UNAUTHENTICATED", "USER_NOT_CONFIRMED"),
    ("login", "initiate_auth", "PasswordResetRequiredException", 401, "UNAUTHENTICATED", "PASSWORD_RESET_REQUIRED"),
    ("login", "initiate_auth", "TooManyRequestsException", 429, "RATE_LIMITED", None),
    ("login", "initiate_auth", "InvalidParameterException", 503, "SERVICE_UNAVAILABLE", None),
    ("login", "initiate_auth", "InvalidUserPoolConfigurationException", 503, "SERVICE_UNAVAILABLE", None),
    ("reauth", "initiate_auth", "NotAuthorizedException", 400, "VALIDATION_ERROR", "INVALID_CURRENT_PASSWORD"),
    ("reauth", "initiate_auth", "UserNotFoundException", 400, "VALIDATION_ERROR", "INVALID_CURRENT_PASSWORD"),
    ("reauth", "initiate_auth", "TooManyRequestsException", 429, "RATE_LIMITED", None),
    ("update", "update_user_attributes", "InvalidParameterException", 400, "VALIDATION_ERROR", "INVALID_PARAMETER"),
    ("update", "update_user_attributes", "NotAuthorizedException", 503, "SERVICE_UNAVAILABLE", None),
    ("update", "update_user_attributes", "TooManyRequestsException", 429, "RATE_LIMITED", None),
    ("get_user", "get_user", "NotAuthorizedException", 401, "UNAUTHENTICATED", None),
    ("get_user", "get_user", "InternalErrorException", 503, "SERVICE_UNAVAILABLE", None),
]


def _invoke(gateway: CognitoGateway, action: str) -> Any:
    calls = {
        "sign_up": lambda: gateway.sign_up(EMAIL, PASSWORD, "Ana", DPI),
        "confirm": lambda: gateway.confirm_sign_up(EMAIL, "123456"),
        "login": lambda: gateway.password_auth(EMAIL, PASSWORD),
        "reauth": lambda: gateway.password_auth(EMAIL, PASSWORD, reauthentication=True),
        "update": lambda: gateway.update_attributes("token", full_name="Ana"),
        "get_user": lambda: gateway.get_user_attributes("token"),
    }
    return calls[action]()


@pytest.mark.parametrize(
    ("action", "method", "aws_code", "status", "code", "reason"),
    ERROR_CASES,
    ids=[f"{c[0]}-{c[2]}" for c in ERROR_CASES],
)
def test_error_mapping(stubbed, action, method, aws_code, status, code, reason) -> None:
    gateway, stubber = stubbed
    _error(stubber, method, aws_code)
    with pytest.raises(ApiError) as info:
        _invoke(gateway, action)
    error = info.value
    assert (error.status_code, error.code) == (status, code)
    assert (error.details or {}).get("reason") == reason
    assert "arn:" not in error.message and "interno" not in error.message


@pytest.mark.parametrize(
    "exc",
    [EndpointConnectionError(endpoint_url="https://cognito-idp"), ReadTimeoutError(endpoint_url="https://cognito-idp")],
    ids=["sin-red", "timeout"],
)
def test_network_errors_are_503(exc: Exception) -> None:
    class Broken:
        def sign_up(self, **_: Any) -> Any:
            raise exc

    with pytest.raises(ApiError) as info:
        CognitoGateway(CLIENT_ID, Broken).sign_up(EMAIL, PASSWORD, "Ana", DPI)
    assert info.value.status_code == 503


def test_client_is_created_lazily_once() -> None:
    created: list[int] = []

    class Ok:
        def confirm_sign_up(self, **_: Any) -> dict[str, Any]:
            return {}

    def factory() -> Ok:
        created.append(1)
        return Ok()

    gateway = CognitoGateway(CLIENT_ID, factory)
    assert created == []
    gateway.confirm_sign_up(EMAIL, "123456")
    gateway.confirm_sign_up(EMAIL, "123456")
    assert created == [1]


def test_logs_have_no_pii_nor_aws_message(stubbed, log_stream) -> None:
    gateway, stubber = stubbed
    _error(stubber, "initiate_auth", "NotAuthorizedException")
    _error(stubber, "sign_up", "InternalErrorException")
    with pytest.raises(ApiError):
        gateway.password_auth(EMAIL, PASSWORD)
    with pytest.raises(ApiError):
        gateway.sign_up(EMAIL, PASSWORD, "Ana Prueba", DPI)
    output = log_stream.getvalue()
    assert "cognito.call" in output and "NotAuthorizedException" in output
    for secret in (EMAIL, PASSWORD, DPI, "Ana Prueba", AWS_INTERNAL_MESSAGE, "arn:aws"):
        assert secret not in output
