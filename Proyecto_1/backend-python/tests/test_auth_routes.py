"""POST /auth/register, /auth/confirm y /auth/login (PRO-14) con dobles.

Cognito y RDS se reemplazan por ``tests/fakes.py``; el mapeo de cada error de
AWS ya se prueba con Stubber en test_cognito_gateway.py. Aquí se prueba el
orden de las operaciones, la consistencia Cognito↔RDS y las respuestas.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.cognito.gateway import SignUpResult
from tests.conftest import (
    COMPLETE_DPI,
    COMPLETE_EMAIL,
    COMPLETE_SUB,
    INCOMPLETE_SUB,
    UNKNOWN_SUB,
    assert_error,
    running,
    seeded_users,
)
from tests.fakes import FakeCognito, challenge, tokens

REGISTER = "/api/v1/auth/register"
CONFIRM = "/api/v1/auth/confirm"
NEW_SUB = "44444444-4444-4444-8444-444444444444"
PASSWORD = "ClaveSegura123!"
VALID = {"fullName": "  Carla Nueva  ", "email": "Carla@Example.com", "dpi": "3333333333333", "password": PASSWORD}


@pytest.fixture
def cognito() -> FakeCognito:
    fake = FakeCognito()
    fake.sign_up_result = SignUpResult(sub=NEW_SUB, confirmed=False)
    return fake


@pytest.fixture
def users():
    return seeded_users()


@pytest.fixture
def api(build_app, cognito, users):
    with running(build_app(cognito_gateway=cognito, users_repository=users)) as client:
        yield client


# --- POST /auth/register ---------------------------------------------------


def test_register_creates_incomplete_profile(api, cognito, users) -> None:
    response = api.post(REGISTER, json=VALID)
    assert response.status_code == 201, response.text
    body = response.json()
    row = users.rows[NEW_SUB]
    assert body == {
        "userId": row.id,
        "email": "carla@example.com",
        "confirmationRequired": True,
        "profileComplete": False,
    }
    assert (row.email, row.full_name, row.dpi, row.profile_image_key) == (
        "carla@example.com",
        "Carla Nueva",
        "3333333333333",
        None,
    )
    assert cognito.calls == [("sign_up", {"email": "carla@example.com", "full_name": "Carla Nueva", "dpi": "3333333333333"})]
    assert PASSWORD not in response.text


def test_register_auto_confirmed_user(api, cognito) -> None:
    cognito.sign_up_result = SignUpResult(sub=NEW_SUB, confirmed=True)
    assert api.post(REGISTER, json=VALID).json()["confirmationRequired"] is False


def test_register_ignores_extra_fields(api, users) -> None:
    payload = {**VALID, "userId": "otro", "faceReferenceKey": "Fotos_Perfil/references/x/y.jpg", "profileComplete": True}
    assert api.post(REGISTER, json=payload).status_code == 201
    assert users.rows[NEW_SUB].face_reference_key is None


@pytest.mark.parametrize(
    "password",
    [
        "Corta123!ab",  # 11 caracteres
        "sinmayuscula123!",
        "SINMINUSCULA123!",
        "SinNumeroAlguno!",
        "SinSimbolo12345",
        "Con Espacio123!",
    ],
    ids=["11-chars", "no-upper", "no-lower", "no-digit", "no-symbol", "whitespace"],
)
def test_register_password_policy_is_checked_before_cognito(api, cognito, password: str) -> None:
    response = api.post(REGISTER, json={**VALID, "password": password})
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "PASSWORD_POLICY"}
    assert "12 caracteres" in body["message"]
    assert password not in response.text
    assert cognito.calls == []


@pytest.mark.parametrize("symbol", list("^$*.[]{}()?\"!@#%&/\\,><':;|_~`=+-"))
def test_register_accepts_every_cognito_symbol(api, symbol: str) -> None:
    assert api.post(REGISTER, json={**VALID, "password": f"ClaveSegura12{symbol}"}).status_code == 201


def test_register_short_password_is_contract_validation_error(api, cognito) -> None:
    body = assert_error(api.post(REGISTER, json={**VALID, "password": "Ab1!"}), 400, "VALIDATION_ERROR")
    assert body["details"]["fields"][0]["field"] == "password"
    assert cognito.calls == []


@pytest.mark.parametrize(
    ("override", "reason"),
    [({"email": COMPLETE_EMAIL.upper()}, "EMAIL_TAKEN"), ({"dpi": COMPLETE_DPI}, "DPI_TAKEN")],
    ids=["email", "dpi"],
)
def test_register_conflict_in_rds_skips_cognito(api, cognito, override: dict, reason: str) -> None:
    body = assert_error(api.post(REGISTER, json={**VALID, **override}), 409, "CONFLICT")
    assert body["details"] == {"reason": reason}
    assert cognito.calls == []


def test_register_rds_down_before_sign_up_is_503(api, cognito, users) -> None:
    users.fail_with = ConnectionError("rds caído")
    assert_error(api.post(REGISTER, json=VALID), 503, "SERVICE_UNAVAILABLE")
    assert cognito.calls == []


@pytest.mark.parametrize(
    "error",
    [
        ApiError(409, "CONFLICT", "Ya existe una cuenta con ese correo.", {"reason": "EMAIL_TAKEN"}),
        ApiError(400, "VALIDATION_ERROR", "x", {"reason": "PASSWORD_POLICY"}),
        ApiError(429, "RATE_LIMITED"),
        ServiceUnavailableError(),
    ],
    ids=["exists", "password", "throttled", "unavailable"],
)
def test_register_cognito_error_creates_no_row(api, cognito, users, error: ApiError) -> None:
    cognito.sign_up_result = error
    assert_error(api.post(REGISTER, json=VALID), error.status_code, error.code)
    assert NEW_SUB not in users.rows


def test_register_insert_failure_logs_orphan_without_pii(api, users, log_stream) -> None:
    original_insert = users.insert

    def broken_insert(**kwargs: Any) -> Any:
        raise ConnectionError("rds caído después de SignUp")

    users.insert = broken_insert  # type: ignore[method-assign]
    assert_error(api.post(REGISTER, json=VALID), 503, "SERVICE_UNAVAILABLE")
    users.insert = original_insert  # type: ignore[method-assign]

    records = [json.loads(line) for line in log_stream.getvalue().splitlines()]
    orphan = [r for r in records if r.get("event") == "auth.register_orphan"]
    assert orphan and orphan[0]["cognitoSub"] == NEW_SUB and orphan[0]["reason"] == "DB_UNAVAILABLE"
    output = log_stream.getvalue()
    for secret in ("carla@example.com", "Carla@Example.com", "3333333333333", PASSWORD, "Carla Nueva"):
        assert secret not in output


def test_register_insert_race_is_409(api, users) -> None:
    def racing_insert(**kwargs: Any) -> Any:
        from app.modules.users.repository import DuplicateUser

        raise DuplicateUser("dpi")

    users.insert = racing_insert  # type: ignore[method-assign]
    body = assert_error(api.post(REGISTER, json=VALID), 409, "CONFLICT")
    assert body["details"] == {"reason": "DPI_TAKEN"}


# --- POST /auth/confirm ----------------------------------------------------


def test_confirm_is_204_without_body(api, cognito) -> None:
    response = api.post(CONFIRM, json={"email": "Carla@Example.com", "code": "123456"})
    assert response.status_code == 204
    assert response.content == b""
    assert cognito.calls == [("confirm_sign_up", {"email": "carla@example.com"})]


@pytest.mark.parametrize(
    "error",
    [
        ApiError(400, "VALIDATION_ERROR", "El código de confirmación no es correcto.", {"reason": "CODE_MISMATCH"}),
        ApiError(400, "VALIDATION_ERROR", "El código de confirmación venció.", {"reason": "CODE_EXPIRED"}),
        ApiError(404, "NOT_FOUND"),
        ApiError(429, "RATE_LIMITED"),
    ],
    ids=["mismatch", "expired", "not-found", "throttled"],
)
def test_confirm_errors(api, cognito, error: ApiError) -> None:
    cognito.confirm_error = error
    body = assert_error(api.post(CONFIRM, json={"email": "a@example.com", "code": "123456"}), error.status_code, error.code)
    assert body["details"] == error.details


@pytest.mark.parametrize("code", ["12345", "123456789"])
def test_confirm_code_length_is_validated_before_cognito(api, cognito, code: str) -> None:
    assert_error(api.post(CONFIRM, json={"email": "a@example.com", "code": code}), 400, "VALIDATION_ERROR")
    assert cognito.calls == []


def test_confirm_logs_have_no_code_nor_email(api, log_stream) -> None:
    api.post(CONFIRM, json={"email": "secreto@example.com", "code": "987654"})
    output = log_stream.getvalue()
    assert "auth.confirmed" in output
    assert "secreto@example.com" not in output and "987654" not in output


# --- POST /auth/login ------------------------------------------------------

LOGIN = "/api/v1/auth/login"
CREDENTIALS = {"email": "Ana@Example.com", "password": PASSWORD}


def _attributes(sub: str, **overrides: str) -> dict[str, str]:
    attributes = {"sub": sub, "email": "nuevo@example.com", "name": "Nuevo Usuario", "custom:dpi": "5555555555555"}
    attributes.update(overrides)
    return attributes


@pytest.mark.parametrize(("sub", "complete"), [(COMPLETE_SUB, True), (INCOMPLETE_SUB, False)])
def test_login_returns_token_set_with_profile_state_from_rds(api, cognito, make_token, sub: str, complete: bool) -> None:
    access = make_token(sub)
    cognito.auth_results = [tokens(access)]
    response = api.post(LOGIN, json=CREDENTIALS)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "accessToken": access,
        "idToken": "id-token",
        "refreshToken": "refresh-token",
        "expiresIn": 3600,
        "tokenType": "Bearer",
        "profileComplete": complete,
    }
    assert cognito.calls == [("password_auth", {"email": "ana@example.com", "reauthentication": False})]


def test_login_challenge_is_202(api, cognito) -> None:
    cognito.auth_results = [challenge("NEW_PASSWORD_REQUIRED")]
    response = api.post(LOGIN, json=CREDENTIALS)
    assert response.status_code == 202
    assert response.json() == {
        "challenge": "NEW_PASSWORD_REQUIRED",
        "session": "s" * 40,
        "parameters": {"requiredAttributes": "[]"},
    }


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ApiError(401, "UNAUTHENTICATED", "Correo o contraseña incorrectos."), None),
        (ApiError(401, "UNAUTHENTICATED", "x", {"reason": "USER_NOT_CONFIRMED"}), "USER_NOT_CONFIRMED"),
        (ApiError(429, "RATE_LIMITED"), None),
        (ServiceUnavailableError(), None),
    ],
    ids=["bad-credentials", "not-confirmed", "throttled", "unavailable"],
)
def test_login_errors(api, cognito, error: ApiError, reason: str | None) -> None:
    cognito.auth_results = [error]
    body = assert_error(api.post(LOGIN, json=CREDENTIALS), error.status_code, error.code)
    assert (body["details"] or {}).get("reason") == reason


def test_login_rejects_token_that_does_not_verify(api, cognito, make_token) -> None:
    cognito.auth_results = [tokens(make_token(COMPLETE_SUB, client_id="otro-cliente"))]
    assert_error(api.post(LOGIN, json=CREDENTIALS), 503, "SERVICE_UNAVAILABLE")


def test_login_ignores_any_bearer_header(api, cognito, make_token) -> None:
    cognito.auth_results = [tokens(make_token(COMPLETE_SUB))]
    response = api.post(LOGIN, json=CREDENTIALS, headers={"Authorization": "Bearer basura"})
    assert response.status_code == 200


def test_login_reconciles_missing_row_from_cognito(api, cognito, users, make_token, log_stream) -> None:
    access = make_token(UNKNOWN_SUB)
    cognito.auth_results = [tokens(access)]
    cognito.user_attributes = _attributes(UNKNOWN_SUB, email="Nuevo@Example.com")
    response = api.post(LOGIN, json=CREDENTIALS)
    assert response.status_code == 200, response.text
    assert response.json()["profileComplete"] is False
    row = users.rows[UNKNOWN_SUB]
    assert (row.email, row.full_name, row.dpi) == ("nuevo@example.com", "Nuevo Usuario", "5555555555555")
    assert ("get_user_attributes", {"access_token": access}) in cognito.calls
    output = log_stream.getvalue()
    assert "users.reconciled" in output
    assert "nuevo@example.com" not in output.lower() and "5555555555555" not in output


@pytest.mark.parametrize(
    ("attributes", "status", "code"),
    [
        (_attributes("otro-sub"), 503, "SERVICE_UNAVAILABLE"),
        (_attributes(UNKNOWN_SUB, **{"custom:dpi": "123"}), 503, "SERVICE_UNAVAILABLE"),
        (_attributes(UNKNOWN_SUB, name=""), 503, "SERVICE_UNAVAILABLE"),
        (_attributes(UNKNOWN_SUB, **{"custom:dpi": COMPLETE_DPI}), 409, "CONFLICT"),
        (ServiceUnavailableError(), 503, "SERVICE_UNAVAILABLE"),
        (ApiError(401, "UNAUTHENTICATED"), 401, "UNAUTHENTICATED"),
    ],
    ids=["sub-mismatch", "bad-dpi", "no-name", "dpi-taken", "get-user-down", "token-revoked"],
)
def test_login_reconciliation_failures(api, cognito, users, make_token, attributes, status: int, code: str) -> None:
    cognito.auth_results = [tokens(make_token(UNKNOWN_SUB))]
    cognito.user_attributes = attributes
    assert_error(api.post(LOGIN, json=CREDENTIALS), status, code)
    assert UNKNOWN_SUB not in users.rows


def test_login_rds_down_is_503(api, cognito, users, make_token) -> None:
    cognito.auth_results = [tokens(make_token(COMPLETE_SUB))]
    users.fail_with = ConnectionError("rds caído")
    assert_error(api.post(LOGIN, json=CREDENTIALS), 503, "SERVICE_UNAVAILABLE")


def test_login_logs_have_no_credentials_nor_tokens(api, cognito, make_token, log_stream) -> None:
    access = make_token(COMPLETE_SUB)
    cognito.auth_results = [tokens(access)]
    api.post(LOGIN, json=CREDENTIALS)
    output = log_stream.getvalue()
    assert "auth.login" in output
    for secret in (access, "id-token", "refresh-token", PASSWORD, "ana@example.com", "Ana@Example.com"):
        assert secret not in output


# --- Caracteres de control y surrogates sueltos (H1/H11) --------------------
# json.loads acepta "\u0000" y "\ud800"; sin la validación de contract.py
# llegaban a psycopg (DataError / UnicodeEncodeError → 503) y, en el registro,
# después de SignUp. Se envían bytes: json.dumps escapa ambos como \uXXXX.

CONTROL_VALUES = {
    "nul": "\x00",
    "newline": "\n",
    "unit-separator": "\x1f",
    "del": "\x7f",
    "c1-nel": "\x85",
    "lone-high-surrogate": "\ud800",
    "lone-low-surrogate": "\udc00",
}
SECRET_VALUES = {"nul": "\x00", "lone-high-surrogate": "\ud800", "lone-low-surrogate": "\udfff"}


def _post_raw(api, url: str, payload: dict) -> Any:
    return api.post(url, content=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})


def _assert_rejected_field(response, field: str) -> None:
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert [f["field"] for f in body["details"]["fields"]] == [field]


@pytest.fixture
def untouched_users(users):
    """Cualquier consulta a RDS lanza; directory.call la convertiría en 503."""
    users.fail_with = AssertionError("no debe consultarse RDS")
    return users


@pytest.mark.parametrize("bad", CONTROL_VALUES.values(), ids=CONTROL_VALUES.keys())
@pytest.mark.parametrize(
    ("field", "template"),
    [("fullName", "Carla{}Nueva"), ("fullName", "Carla Nueva{}"), ("email", "carla{}@example.com"), ("email", "carla@example.com{}")],
    ids=["name-middle", "name-trailing", "email-middle", "email-trailing"],
)
def test_register_rejects_control_characters_before_cognito(
    api, cognito, untouched_users, field: str, template: str, bad: str
) -> None:
    _assert_rejected_field(_post_raw(api, REGISTER, {**VALID, field: template.format(bad)}), field)
    assert cognito.calls == []
    assert NEW_SUB not in untouched_users.rows


@pytest.mark.parametrize("bad", SECRET_VALUES.values(), ids=SECRET_VALUES.keys())
def test_register_rejects_nul_or_lone_surrogate_in_password(api, cognito, untouched_users, bad: str) -> None:
    response = _post_raw(api, REGISTER, {**VALID, "password": f"ClaveSegura{bad}123!"})
    _assert_rejected_field(response, "password")
    assert "ClaveSegura" not in response.text
    assert cognito.calls == []


def test_register_rejects_raw_utf8_encoded_surrogate(api, cognito, untouched_users) -> None:
    # Bytes ED A0 80 (U+D800 en CESU-8): json.loads los decodifica con surrogatepass.
    raw = json.dumps({**VALID, "fullName": "Carla_SURR_Nueva"}).encode().replace(b"_SURR_", b"\xed\xa0\x80")
    response = api.post(REGISTER, content=raw, headers={"Content-Type": "application/json"})
    _assert_rejected_field(response, "fullName")
    assert cognito.calls == []


@pytest.mark.parametrize("ensure_ascii", [True, False], ids=["escaped", "utf8"])
def test_register_accepts_accents_enye_and_emoji(api, cognito, users, ensure_ascii: bool) -> None:
    # Con ensure_ascii el emoji viaja como par de surrogates escapado y llega combinado.
    name = "José Ñandú Pérez 😀👩‍💻"
    payload = json.dumps({**VALID, "fullName": name}, ensure_ascii=ensure_ascii).encode()
    response = api.post(REGISTER, content=payload, headers={"Content-Type": "application/json"})
    assert response.status_code == 201, response.text
    assert users.rows[NEW_SUB].full_name == name
    assert cognito.calls[0][1]["full_name"] == name


@pytest.mark.parametrize("bad", CONTROL_VALUES.values(), ids=CONTROL_VALUES.keys())
@pytest.mark.parametrize(
    ("field", "payload"),
    [("code", {"email": "a@example.com", "code": "123{}45"}), ("email", {"email": "a{}@example.com", "code": "123456"})],
    ids=["code", "email"],
)
def test_confirm_rejects_control_characters_before_cognito(api, cognito, untouched_users, field: str, payload: dict, bad: str) -> None:
    payload = {key: value.format(bad) for key, value in payload.items()}
    _assert_rejected_field(_post_raw(api, CONFIRM, payload), field)
    assert cognito.calls == []


@pytest.mark.parametrize("bad", CONTROL_VALUES.values(), ids=CONTROL_VALUES.keys())
def test_login_rejects_control_characters_in_email_before_cognito(api, cognito, untouched_users, bad: str) -> None:
    _assert_rejected_field(_post_raw(api, LOGIN, {**CREDENTIALS, "email": f"ana{bad}@example.com"}), "email")
    assert cognito.calls == []


@pytest.mark.parametrize("bad", SECRET_VALUES.values(), ids=SECRET_VALUES.keys())
def test_login_rejects_nul_or_lone_surrogate_in_password_before_cognito(api, cognito, untouched_users, bad: str) -> None:
    _assert_rejected_field(_post_raw(api, LOGIN, {**CREDENTIALS, "password": f"Clave{bad}Segura123!"}), "password")
    assert cognito.calls == []


def test_login_password_keeps_other_symbols_for_cognito(api, cognito) -> None:
    # Solo NUL y surrogates se rechazan en contraseñas; el resto lo decide Cognito.
    cognito.auth_results = [ApiError(401, "UNAUTHENTICATED")]
    response = _post_raw(api, LOGIN, {**CREDENTIALS, "password": "Clave\tSegura123!ñ€"})
    assert_error(response, 401, "UNAUTHENTICATED")
    assert cognito.names() == ["password_auth"]
