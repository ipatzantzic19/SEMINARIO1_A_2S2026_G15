"""CognitoGateway del login facial (CUSTOM_AUTH) con Stubber. Ninguna prueba llama a AWS."""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.stub import Stubber

from app.common.errors import ApiError
from app.common.logs import build_handler
from app.modules.integrations.cognito.gateway import AuthChallenge, AuthTokens, CognitoGateway

CLIENT_ID = "test-client-id"
POOL_ID = "us-east-1_testPool"
EMAIL = "ana@example.com"
SUB = "11111111-1111-4111-8111-111111111111"
SESSION = "S" * 60
ANSWER = '{"challengeId":"c","purpose":"faceCapture","captureKey":"Fotos_Perfil/captures/c/x.jpg"}'
REFERENCE = f"Fotos_Perfil/references/{SUB}/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.jpg"
AWS_MESSAGE = "arn:aws:lambda:us-east-1:123456789012:function:interno mensaje interno de AWS"


@pytest.fixture
def stubbed() -> Iterator[tuple[CognitoGateway, Stubber]]:
    client = boto3.client("cognito-idp", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    with Stubber(client) as stubber:
        yield CognitoGateway(CLIENT_ID, lambda: client, user_pool_id=POOL_ID), stubber
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


def _error(stubber: Stubber, method: str, code: str, message: str = AWS_MESSAGE) -> None:
    stubber.add_client_error(method, service_error_code=code, service_message=message, http_status_code=400)


# --- llamadas exitosas -----------------------------------------------------


def test_initiate_custom_auth_sends_custom_flow_and_returns_challenge(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "initiate_auth",
        {
            "ChallengeName": "CUSTOM_CHALLENGE",
            "Session": SESSION,
            "ChallengeParameters": {"challengeId": "cid", "purpose": "faceCapture", "expiresInSeconds": "120", "USERNAME": SUB},
        },
        {"ClientId": CLIENT_ID, "AuthFlow": "CUSTOM_AUTH", "AuthParameters": {"USERNAME": EMAIL}},
    )
    outcome = gateway.initiate_custom_auth(EMAIL)
    assert outcome == AuthChallenge(
        "CUSTOM_CHALLENGE", SESSION,
        {"challengeId": "cid", "purpose": "faceCapture", "expiresInSeconds": "120", "USERNAME": SUB},
    )


def test_respond_sends_answer_session_and_username(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "respond_to_auth_challenge",
        {"AuthenticationResult": {"AccessToken": "a", "IdToken": "i", "RefreshToken": "r", "ExpiresIn": 3600, "TokenType": "Bearer"}},
        {
            "ClientId": CLIENT_ID,
            "ChallengeName": "CUSTOM_CHALLENGE",
            "Session": SESSION,
            "ChallengeResponses": {"USERNAME": SUB, "ANSWER": ANSWER},
        },
    )
    assert gateway.respond_to_custom_challenge(username=SUB, session=SESSION, answer=ANSWER) == AuthTokens("a", "i", "r", 3600)


def test_respond_may_return_another_challenge(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "respond_to_auth_challenge",
        {"ChallengeName": "CUSTOM_CHALLENGE", "Session": "N" * 60, "ChallengeParameters": {"challengeId": "otro"}},
    )
    outcome = gateway.respond_to_custom_challenge(username=SUB, session=SESSION, answer=ANSWER)
    assert isinstance(outcome, AuthChallenge) and outcome.name == "CUSTOM_CHALLENGE"


def test_respond_with_incomplete_tokens_is_503(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response("respond_to_auth_challenge", {"AuthenticationResult": {"AccessToken": "a", "ExpiresIn": 3600}})
    with pytest.raises(ApiError) as info:
        gateway.respond_to_custom_challenge(username=SUB, session=SESSION, answer=ANSWER)
    assert info.value.status_code == 503


def test_update_face_reference_uses_admin_api_with_pool_and_sub(stubbed) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "admin_update_user_attributes",
        {},
        {
            "UserPoolId": POOL_ID,
            "Username": SUB,
            "UserAttributes": [{"Name": "custom:face_reference_key", "Value": REFERENCE}],
        },
    )
    gateway.update_face_reference(SUB, REFERENCE)


def test_update_face_reference_without_pool_id_is_503() -> None:
    called: list[int] = []
    gateway = CognitoGateway(CLIENT_ID, lambda: called.append(1))
    with pytest.raises(ApiError) as info:
        gateway.update_face_reference(SUB, REFERENCE)
    assert info.value.status_code == 503 and called == []


# --- mapeo de errores ------------------------------------------------------

INITIATE_CASES = [
    # (código AWS, mensaje, estado, code, reason)
    ("NotAuthorizedException", AWS_MESSAGE, 401, "UNAUTHENTICATED", "FACE_UNKNOWN_USER"),
    ("UserNotFoundException", AWS_MESSAGE, 401, "UNAUTHENTICATED", "FACE_UNKNOWN_USER"),
    ("UserNotConfirmedException", AWS_MESSAGE, 401, "UNAUTHENTICATED", "USER_NOT_CONFIRMED"),
    ("PasswordResetRequiredException", AWS_MESSAGE, 401, "UNAUTHENTICATED", "PASSWORD_RESET_REQUIRED"),
    (
        "UserLambdaValidationException",
        "CreateAuthChallenge failed with error MISSING_FACE_REFERENCE.",
        400, "VALIDATION_ERROR", "FACE_REFERENCE_MISSING",
    ),
    ("UserLambdaValidationException", "CreateAuthChallenge failed with error OTRO_ERROR.", 503, "SERVICE_UNAVAILABLE", None),
    ("InvalidLambdaResponseException", AWS_MESSAGE, 503, "SERVICE_UNAVAILABLE", None),
    ("UnexpectedLambdaException", AWS_MESSAGE, 503, "SERVICE_UNAVAILABLE", None),
    ("InvalidParameterException", AWS_MESSAGE, 503, "SERVICE_UNAVAILABLE", None),
    ("TooManyRequestsException", AWS_MESSAGE, 429, "RATE_LIMITED", None),
    ("LimitExceededException", AWS_MESSAGE, 429, "RATE_LIMITED", None),
    ("InternalErrorException", AWS_MESSAGE, 503, "SERVICE_UNAVAILABLE", None),
]


@pytest.mark.parametrize(("aws_code", "message", "status", "code", "reason"), INITIATE_CASES,
                         ids=[f"init-{i}-{c[0]}" for i, c in enumerate(INITIATE_CASES)])
def test_initiate_error_mapping(stubbed, aws_code, message, status, code, reason) -> None:
    gateway, stubber = stubbed
    _error(stubber, "initiate_auth", aws_code, message)
    with pytest.raises(ApiError) as info:
        gateway.initiate_custom_auth(EMAIL)
    error = info.value
    assert (error.status_code, error.code) == (status, code)
    assert (error.details or {}).get("reason") == reason
    assert "arn:" not in error.message and "interno" not in error.message and "OTRO_ERROR" not in error.message


RESPOND_CASES = [
    ("NotAuthorizedException", 422, "FACE_NOT_MATCHED"),
    ("UserNotFoundException", 422, "FACE_NOT_MATCHED"),
    ("TooManyRequestsException", 429, "RATE_LIMITED"),
    ("UserLambdaValidationException", 503, "SERVICE_UNAVAILABLE"),
    ("InvalidLambdaResponseException", 503, "SERVICE_UNAVAILABLE"),
    ("ExpiredCodeException", 503, "SERVICE_UNAVAILABLE"),
    ("InternalErrorException", 503, "SERVICE_UNAVAILABLE"),
]


@pytest.mark.parametrize(("aws_code", "status", "code"), RESPOND_CASES, ids=[c[0] for c in RESPOND_CASES])
def test_respond_error_mapping(stubbed, aws_code, status, code) -> None:
    gateway, stubber = stubbed
    _error(stubber, "respond_to_auth_challenge", aws_code)
    with pytest.raises(ApiError) as info:
        gateway.respond_to_custom_challenge(username=SUB, session=SESSION, answer=ANSWER)
    assert (info.value.status_code, info.value.code) == (status, code)
    assert "arn:" not in info.value.message and "interno" not in info.value.message


def test_missing_reference_marker_is_only_read_for_initiate(stubbed) -> None:
    """En RespondToAuthChallenge el mismo texto no cambia el mapeo (503, no 400)."""
    gateway, stubber = stubbed
    _error(stubber, "respond_to_auth_challenge", "UserLambdaValidationException", "failed with error MISSING_FACE_REFERENCE.")
    with pytest.raises(ApiError) as info:
        gateway.respond_to_custom_challenge(username=SUB, session=SESSION, answer=ANSWER)
    assert info.value.status_code == 503


@pytest.mark.parametrize("aws_code", ["AccessDeniedException", "UserNotFoundException", "InternalErrorException"])
def test_update_face_reference_errors_are_503(stubbed, aws_code) -> None:
    gateway, stubber = stubbed
    _error(stubber, "admin_update_user_attributes", aws_code)
    with pytest.raises(ApiError) as info:
        gateway.update_face_reference(SUB, REFERENCE)
    assert info.value.status_code == 503


def test_update_face_reference_throttling_is_429(stubbed) -> None:
    gateway, stubber = stubbed
    _error(stubber, "admin_update_user_attributes", "TooManyRequestsException")
    with pytest.raises(ApiError) as info:
        gateway.update_face_reference(SUB, REFERENCE)
    assert info.value.status_code == 429


def test_logs_have_no_session_answer_email_nor_aws_message(stubbed, log_stream) -> None:
    gateway, stubber = stubbed
    stubber.add_response(
        "initiate_auth",
        {"ChallengeName": "CUSTOM_CHALLENGE", "Session": SESSION, "ChallengeParameters": {"challengeId": "cid"}},
    )
    gateway.initiate_custom_auth(EMAIL)
    _error(stubber, "initiate_auth", "UserLambdaValidationException", "failed with error MISSING_FACE_REFERENCE. " + AWS_MESSAGE)
    with pytest.raises(ApiError):
        gateway.initiate_custom_auth(EMAIL)
    _error(stubber, "respond_to_auth_challenge", "NotAuthorizedException")
    with pytest.raises(ApiError):
        gateway.respond_to_custom_challenge(username=SUB, session=SESSION, answer=ANSWER)
    stubber.add_response("admin_update_user_attributes", {})
    gateway.update_face_reference(SUB, REFERENCE)
    logs = log_stream.getvalue()
    assert logs
    for secret in (EMAIL, SESSION, ANSWER, "captureKey", REFERENCE, "interno", "arn:", "MISSING_FACE_REFERENCE:"):
        assert secret not in logs
