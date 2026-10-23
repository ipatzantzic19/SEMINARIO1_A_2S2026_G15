"""GET /me, POST /me/complete-profile y PATCH /me (PRO-14) con dobles."""

from __future__ import annotations

import json

import pytest

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.s3.objects import ObjectInfo
from tests.conftest import (
    COMPLETE_DPI,
    COMPLETE_EMAIL,
    COMPLETE_SUB,
    INCOMPLETE_DPI,
    INCOMPLETE_EMAIL,
    INCOMPLETE_SUB,
    UNKNOWN_SUB,
    assert_error,
    running,
    seeded_users,
)
from tests.fakes import FakeCognito, FakeImageObjects, challenge, tokens

ME = "/api/v1/me"
BUCKET_URL = "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/"


@pytest.fixture
def users():
    return seeded_users()


@pytest.fixture
def cognito() -> FakeCognito:
    return FakeCognito()


@pytest.fixture
def images() -> FakeImageObjects:
    return FakeImageObjects()


@pytest.fixture
def api(build_app, users, cognito, images):
    with running(build_app(users_repository=users, cognito_gateway=cognito, image_objects=images)) as client:
        yield client


# --- GET /me ---------------------------------------------------------------


def test_get_me_complete_profile(api, users, auth_header) -> None:
    row = users.rows[COMPLETE_SUB]
    response = api.get(ME, headers=auth_header(COMPLETE_SUB))
    assert response.status_code == 200
    assert response.json() == {
        "userId": row.id,
        "fullName": "Ana Completa",
        "email": COMPLETE_EMAIL,
        "dpi": COMPLETE_DPI,
        "profileImageUrl": BUCKET_URL + row.profile_image_key,
        "profileComplete": True,
    }


def test_get_me_incomplete_profile_has_null_image(api, auth_header) -> None:
    body = api.get(ME, headers=auth_header(INCOMPLETE_SUB)).json()
    assert body["profileComplete"] is False and body["profileImageUrl"] is None
    assert (body["email"], body["dpi"]) == (INCOMPLETE_EMAIL, INCOMPLETE_DPI)


def test_get_me_does_not_expose_internal_fields(api, auth_header) -> None:
    body = api.get(ME, headers=auth_header(COMPLETE_SUB)).json()
    assert not {"cognitoSub", "faceReferenceKey", "profileImageKey"} & set(body)


def test_get_me_reconciles_missing_row(api, users, cognito, make_token) -> None:
    token = make_token(UNKNOWN_SUB)
    cognito.user_attributes = {"sub": UNKNOWN_SUB, "email": "nuevo@example.com", "name": "Nuevo", "custom:dpi": "5555555555555"}
    response = api.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.json()["profileComplete"] is False
    assert users.rows[UNKNOWN_SUB].dpi == "5555555555555"
    assert cognito.calls == [("get_user_attributes", {"access_token": token})]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(ServiceUnavailableError(), 503, "SERVICE_UNAVAILABLE"), (ApiError(401, "UNAUTHENTICATED"), 401, "UNAUTHENTICATED")],
    ids=["get-user-down", "token-revoked"],
)
def test_get_me_reconciliation_errors(api, users, cognito, auth_header, error, status, code) -> None:
    cognito.user_attributes = error
    assert_error(api.get(ME, headers=auth_header(UNKNOWN_SUB)), status, code)
    assert UNKNOWN_SUB not in users.rows


def test_get_me_rds_down_is_503(api, users, cognito, auth_header) -> None:
    users.fail_with = ConnectionError("rds caído")
    assert_error(api.get(ME, headers=auth_header(COMPLETE_SUB)), 503, "SERVICE_UNAVAILABLE")
    assert cognito.calls == []


def test_get_me_logs_have_no_pii(api, auth_header, log_stream) -> None:
    header = auth_header(COMPLETE_SUB)
    api.get(ME, headers=header)
    output = log_stream.getvalue()
    for secret in (COMPLETE_EMAIL, COMPLETE_DPI, header["Authorization"].split()[1]):
        assert secret not in output


# --- POST /me/complete-profile ---------------------------------------------

COMPLETE_PROFILE = "/api/v1/me/complete-profile"
FILE = "0b6f6c4e-873e-486a-847e-aeaf52aa4e2e.jpg"
PUBLIC_KEY = f"Fotos_Perfil/public/{INCOMPLETE_SUB}/{FILE}"
REFERENCE_KEY = f"Fotos_Perfil/references/{INCOMPLETE_SUB}/{FILE}"
JPEG = ObjectInfo("image/jpeg", 120_000)


def _uploaded(images: FakeImageObjects, *, public: ObjectInfo | None = JPEG, reference: ObjectInfo | None = JPEG) -> None:
    if public is not None:
        images.objects[PUBLIC_KEY] = public
    if reference is not None:
        images.objects[REFERENCE_KEY] = reference


def test_complete_profile_sets_photo_and_server_side_reference(api, users, images, auth_header) -> None:
    _uploaded(images)
    response = api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=auth_header(INCOMPLETE_SUB))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profileComplete"] is True
    assert body["profileImageUrl"] == BUCKET_URL + PUBLIC_KEY
    row = users.rows[INCOMPLETE_SUB]
    assert (row.profile_image_key, row.face_reference_key) == (PUBLIC_KEY, REFERENCE_KEY)
    assert images.heads == [PUBLIC_KEY, REFERENCE_KEY]


def test_complete_profile_enables_social_routes(api, images, auth_header) -> None:
    header = auth_header(INCOMPLETE_SUB)
    assert_error(api.get("/api/v1/friends", headers=header), 403, "FORBIDDEN")
    _uploaded(images)
    assert api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=header).status_code == 200
    # PRO-34 aún pendiente: 501 demuestra que require_complete_profile ya no bloquea.
    assert_error(api.get("/api/v1/posts", headers=header), 501, "NOT_IMPLEMENTED")


def test_client_cannot_choose_face_reference(api, users, images, auth_header) -> None:
    _uploaded(images)
    payload = {"profileImageKey": PUBLIC_KEY, "faceReferenceKey": f"Fotos_Perfil/references/{COMPLETE_SUB}/{FILE}"}
    assert api.post(COMPLETE_PROFILE, json=payload, headers=auth_header(INCOMPLETE_SUB)).status_code == 200
    assert users.rows[INCOMPLETE_SUB].face_reference_key == REFERENCE_KEY


@pytest.mark.parametrize(
    "key",
    [
        f"Fotos_Perfil/references/{INCOMPLETE_SUB}/{FILE}",
        f"Fotos_Perfil/captures/{INCOMPLETE_SUB}/{FILE}",
        f"Fotos_Publicadas/{INCOMPLETE_SUB}/{FILE}",
        f"Fotos_Perfil/public/{INCOMPLETE_SUB}/../{COMPLETE_SUB}/{FILE}",
        f"Fotos_Perfil/public/{INCOMPLETE_SUB}/sub/{FILE}",
        f"Fotos_Perfil/public/{INCOMPLETE_SUB}/{FILE.upper()}",
        f"Fotos_Perfil/public/{INCOMPLETE_SUB}/{FILE[:-4]}.bin",
        f"Fotos_Perfil/public/{INCOMPLETE_SUB}/foto.jpg",
        f"https://bucket.s3.amazonaws.com/{PUBLIC_KEY}",
        f"/{PUBLIC_KEY}",
    ],
    ids=["references", "captures", "posts", "traversal", "nested", "uppercase", "bin", "not-uuid", "url", "leading-slash"],
)
def test_complete_profile_rejects_malformed_keys_without_s3(api, images, auth_header, key: str) -> None:
    body = assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": key}, headers=auth_header(INCOMPLETE_SUB)), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_IMAGE_KEY"}
    assert images.heads == []


def test_complete_profile_rejects_key_of_another_user(api, images, auth_header) -> None:
    key = f"Fotos_Perfil/public/{COMPLETE_SUB}/{FILE}"
    images.objects[key] = JPEG
    body = assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": key}, headers=auth_header(INCOMPLETE_SUB)), 403, "FORBIDDEN")
    assert body["details"] == {"reason": "IMAGE_KEY_NOT_OWNED"}
    assert images.heads == []


@pytest.mark.parametrize(
    ("public", "reference", "reason"),
    [
        (None, JPEG, "PROFILE_IMAGE_NOT_FOUND"),
        (JPEG, None, "FACE_REFERENCE_NOT_FOUND"),
        (ObjectInfo("image/gif", 100), JPEG, "PROFILE_IMAGE_INVALID"),
        (ObjectInfo(None, 100), JPEG, "PROFILE_IMAGE_INVALID"),
        (ObjectInfo("image/png", 5 * 1024 * 1024 + 1), JPEG, "PROFILE_IMAGE_INVALID"),
    ],
    ids=["no-public", "no-reference", "gif", "no-content-type", "too-large"],
)
def test_complete_profile_checks_objects_in_s3(api, users, images, auth_header, public, reference, reason: str) -> None:
    _uploaded(images, public=public, reference=reference)
    body = assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=auth_header(INCOMPLETE_SUB)), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": reason}
    assert users.rows[INCOMPLETE_SUB].profile_image_key is None


def test_complete_profile_s3_unavailable_is_503(api, users, images, auth_header) -> None:
    images.error = ServiceUnavailableError()
    assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=auth_header(INCOMPLETE_SUB)), 503, "SERVICE_UNAVAILABLE")
    assert users.rows[INCOMPLETE_SUB].profile_image_key is None


def test_complete_profile_twice_is_409(api, images, auth_header) -> None:
    key = f"Fotos_Perfil/public/{COMPLETE_SUB}/{FILE}"
    body = assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": key}, headers=auth_header(COMPLETE_SUB)), 409, "CONFLICT")
    assert body["details"] == {"reason": "PROFILE_ALREADY_COMPLETE"}
    assert images.heads == []


def test_complete_profile_race_is_409(api, users, images, auth_header) -> None:
    _uploaded(images)
    users.complete_profile = lambda *args: None  # type: ignore[method-assign]
    assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=auth_header(INCOMPLETE_SUB)), 409, "CONFLICT")


def test_complete_profile_reconciles_missing_row_first(api, users, cognito, images, make_token) -> None:
    file_key = f"Fotos_Perfil/public/{UNKNOWN_SUB}/{FILE}"
    images.objects[file_key] = JPEG
    images.objects[f"Fotos_Perfil/references/{UNKNOWN_SUB}/{FILE}"] = JPEG
    cognito.user_attributes = {"sub": UNKNOWN_SUB, "email": "n@example.com", "name": "Nuevo", "custom:dpi": "5555555555555"}
    response = api.post(COMPLETE_PROFILE, json={"profileImageKey": file_key}, headers={"Authorization": f"Bearer {make_token(UNKNOWN_SUB)}"})
    assert response.status_code == 200, response.text
    assert users.rows[UNKNOWN_SUB].profile_complete


def test_complete_profile_rds_down_is_503(api, users, auth_header) -> None:
    users.fail_with = ConnectionError("rds caído")
    assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=auth_header(INCOMPLETE_SUB)), 503, "SERVICE_UNAVAILABLE")


def test_complete_profile_requires_token(api) -> None:
    assert_error(api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}), 401, "UNAUTHENTICATED")


def test_complete_profile_logs_have_no_keys_nor_pii(api, images, auth_header, log_stream) -> None:
    _uploaded(images)
    api.post(COMPLETE_PROFILE, json={"profileImageKey": PUBLIC_KEY}, headers=auth_header(INCOMPLETE_SUB))
    output = log_stream.getvalue()
    assert "profile.completed" in output
    for secret in (PUBLIC_KEY, REFERENCE_KEY, INCOMPLETE_EMAIL, INCOMPLETE_DPI):
        assert secret not in output


# --- PATCH /me ---------------------------------------------------------------

CURRENT = "ClaveActual123!"


@pytest.fixture
def fresh(cognito, make_token) -> str:
    """Access token que devuelve Cognito al verificar currentPassword."""
    token = make_token(COMPLETE_SUB)
    cognito.auth_results = [tokens(token)]
    return token


def _patch(api, auth_header, payload: dict, sub: str = COMPLETE_SUB):
    return api.patch(ME, json={"currentPassword": CURRENT, **payload}, headers=auth_header(sub))


def _code(status: int) -> str:
    return {400: "VALIDATION_ERROR", 403: "FORBIDDEN"}[status]


def test_patch_me_syncs_cognito_and_rds(api, users, cognito, auth_header, fresh) -> None:
    response = _patch(api, auth_header, {"fullName": "  Ana Editada ", "dpi": "9999999999999"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["fullName"], body["dpi"], body["profileComplete"]) == ("Ana Editada", "9999999999999", True)
    row = users.rows[COMPLETE_SUB]
    assert (row.full_name, row.dpi) == ("Ana Editada", "9999999999999")
    assert cognito.calls == [
        ("password_auth", {"email": COMPLETE_EMAIL, "reauthentication": True}),
        ("update_attributes", {"access_token": fresh, "full_name": "Ana Editada", "dpi": "9999999999999"}),
    ]


@pytest.mark.parametrize(
    "error",
    [
        ApiError(
            400,
            "VALIDATION_ERROR",
            "La contraseña actual no es correcta. No se realizaron cambios.",
            {"reason": "INVALID_CURRENT_PASSWORD"},
        ),
        ApiError(429, "RATE_LIMITED"),
    ],
    ids=["wrong-password", "throttled"],
)
def test_patch_me_bad_current_password_changes_nothing(api, users, cognito, auth_header, error) -> None:
    before = users.rows[COMPLETE_SUB]
    cognito.auth_results = [error]
    response = _patch(api, auth_header, {"fullName": "Otro Nombre", "dpi": "9999999999999"})
    assert response.status_code != 401  # un 401 cerraría la sesión en el frontend
    assert_error(response, error.status_code, error.code)
    assert users.rows[COMPLETE_SUB] == before
    assert "update_attributes" not in cognito.names()


def test_patch_me_reauth_challenge_is_400(api, cognito, auth_header) -> None:
    cognito.auth_results = [challenge()]
    body = assert_error(_patch(api, auth_header, {"fullName": "Otro Nombre"}), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "REAUTHENTICATION_CHALLENGE"}


def test_patch_me_reauth_for_other_identity_changes_nothing(api, users, cognito, auth_header, make_token) -> None:
    before = users.rows[COMPLETE_SUB]
    cognito.auth_results = [tokens(make_token(INCOMPLETE_SUB))]
    body = assert_error(_patch(api, auth_header, {"fullName": "Otro Nombre"}), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_CURRENT_PASSWORD"}
    assert users.rows[COMPLETE_SUB] == before


def test_patch_me_duplicate_dpi_is_409_before_cognito(api, users, cognito, auth_header, fresh) -> None:
    body = assert_error(_patch(api, auth_header, {"dpi": INCOMPLETE_DPI}), 409, "CONFLICT")
    assert body["details"] == {"reason": "DPI_TAKEN"}
    assert "update_attributes" not in cognito.names()
    assert users.rows[COMPLETE_SUB].dpi == COMPLETE_DPI


@pytest.mark.parametrize(
    "error",
    [
        ServiceUnavailableError(),
        ApiError(400, "VALIDATION_ERROR", "x", {"reason": "INVALID_PARAMETER"}),
        ApiError(429, "RATE_LIMITED"),
    ],
    ids=["unavailable", "invalid", "throttled"],
)
def test_patch_me_cognito_failure_rolls_back_rds(api, users, cognito, auth_header, fresh, error) -> None:
    before = users.rows[COMPLETE_SUB]
    cognito.update_error = error
    assert_error(_patch(api, auth_header, {"fullName": "Otro Nombre"}), error.status_code, error.code)
    assert users.rows[COMPLETE_SUB] == before


def test_patch_me_commit_failure_reverts_cognito(api, users, cognito, auth_header, fresh, log_stream) -> None:
    before = users.rows[COMPLETE_SUB]
    users.fail_commit = True
    response = _patch(api, auth_header, {"fullName": "Otro Nombre", "dpi": "9999999999999"})
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    updates = [kwargs for name, kwargs in cognito.calls if name == "update_attributes"]
    assert updates == [
        {"access_token": fresh, "full_name": "Otro Nombre", "dpi": "9999999999999"},
        {"access_token": fresh, "full_name": "Ana Completa", "dpi": COMPLETE_DPI},
    ]
    assert users.rows[COMPLETE_SUB] == before
    assert "profile.cognito_reverted" in log_stream.getvalue()


def test_patch_me_commit_failure_with_failed_revert_is_logged(api, users, cognito, auth_header, fresh, log_stream) -> None:
    users.fail_commit = True
    cognito.update_errors = [None, ServiceUnavailableError()]
    assert_error(_patch(api, auth_header, {"fullName": "Otro Nombre"}), 503, "SERVICE_UNAVAILABLE")
    output = log_stream.getvalue()
    assert "profile.cognito_revert_failed" in output and COMPLETE_SUB in output
    assert "Otro Nombre" not in output and "Ana Completa" not in output


def test_patch_me_without_changes_only_checks_password(api, cognito, auth_header, fresh) -> None:
    response = _patch(api, auth_header, {"fullName": "Ana Completa", "dpi": COMPLETE_DPI})
    assert response.status_code == 200
    assert cognito.names() == ["password_auth"]


def test_patch_me_new_photo_is_verified_and_not_sent_to_cognito(api, users, cognito, images, auth_header, fresh) -> None:
    public = f"Fotos_Perfil/public/{COMPLETE_SUB}/{FILE}"
    reference = f"Fotos_Perfil/references/{COMPLETE_SUB}/{FILE}"
    images.objects.update({public: JPEG, reference: JPEG})
    response = _patch(api, auth_header, {"profileImageKey": public})
    assert response.status_code == 200, response.text
    assert response.json()["profileImageUrl"] == BUCKET_URL + public
    row = users.rows[COMPLETE_SUB]
    assert (row.profile_image_key, row.face_reference_key) == (public, reference)
    assert "update_attributes" not in cognito.names()


@pytest.mark.parametrize(
    ("key", "status", "reason"),
    [
        (f"Fotos_Perfil/public/{INCOMPLETE_SUB}/{FILE}", 403, "IMAGE_KEY_NOT_OWNED"),
        (f"Fotos_Perfil/public/{COMPLETE_SUB}/{FILE}", 400, "PROFILE_IMAGE_NOT_FOUND"),
        ("Fotos_Perfil/references/x/y.jpg", 400, "INVALID_IMAGE_KEY"),
    ],
    ids=["other-user", "missing", "malformed"],
)
def test_patch_me_invalid_photo_changes_nothing(api, users, cognito, auth_header, fresh, key, status, reason) -> None:
    before = users.rows[COMPLETE_SUB]
    response = _patch(api, auth_header, {"fullName": "Otro Nombre", "profileImageKey": key})
    body = assert_error(response, status, _code(status))
    assert body["details"] == {"reason": reason}
    assert users.rows[COMPLETE_SUB] == before
    assert "update_attributes" not in cognito.names()


def test_user_cannot_edit_another_user(api, users, auth_header, fresh) -> None:
    other = users.add(UNKNOWN_SUB, email="otro@example.com", full_name="Otra Persona", dpi="7777777777777", complete=True)
    payload = {"userId": other.id, "cognitoSub": UNKNOWN_SUB, "email": "otro@example.com", "fullName": "Cambiado"}
    response = _patch(api, auth_header, payload)
    assert response.status_code == 200
    assert response.json()["userId"] == users.rows[COMPLETE_SUB].id
    assert users.rows[UNKNOWN_SUB] == other
    assert users.rows[COMPLETE_SUB].email == COMPLETE_EMAIL  # el correo no es editable


@pytest.mark.parametrize(
    "payload",
    [
        {"fullName": "Ana"},
        {"currentPassword": "", "fullName": "Ana"},
        {"currentPassword": CURRENT, "dpi": "12"},
        {"currentPassword": CURRENT, "fullName": " "},
    ],
    ids=["no-password", "empty-password", "bad-dpi", "blank-name"],
)
def test_patch_me_body_validation(api, cognito, auth_header, payload: dict) -> None:
    assert_error(api.patch(ME, json=payload, headers=auth_header(COMPLETE_SUB)), 400, "VALIDATION_ERROR")
    assert cognito.calls == []


def test_patch_me_incomplete_profile_is_403_without_cognito(api, cognito, auth_header) -> None:
    body = assert_error(_patch(api, auth_header, {"fullName": "Bruno"}, sub=INCOMPLETE_SUB), 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}
    assert cognito.calls == []


def test_patch_me_logs_have_no_password_dpi_nor_tokens(api, auth_header, fresh, log_stream) -> None:
    header = auth_header(COMPLETE_SUB)
    api.patch(ME, json={"currentPassword": CURRENT, "dpi": "9999999999999"}, headers=header)
    output = log_stream.getvalue()
    assert "profile.updated" in output
    for secret in (CURRENT, "9999999999999", COMPLETE_DPI, COMPLETE_EMAIL, fresh, header["Authorization"].split()[1]):
        assert secret not in output


# --- Caracteres de control y surrogates sueltos (H1/H11) --------------------
# Se envían bytes: json.dumps escapa "\x00" y "\ud800" como \uXXXX y
# json.loads los reconstruye tal cual en el servidor.

PATCH_CONTROL_VALUES = {
    "nul": "\x00",
    "newline": "\n",
    "del": "\x7f",
    "c1-nel": "\x85",
    "lone-high-surrogate": "\ud800",
    "lone-low-surrogate": "\udc00",
}


def _patch_raw(api, auth_header, payload: dict):
    headers = {**auth_header(COMPLETE_SUB), "Content-Type": "application/json"}
    return api.patch(ME, content=json.dumps(payload).encode(), headers=headers)


@pytest.fixture
def guarded_users(users, monkeypatch):
    """Solo la dependencia require_complete_profile puede leer RDS; cualquier
    otra consulta lanza y directory.call la convertiría en 503."""

    def forbidden(*args, **kwargs):
        raise AssertionError("no debe consultarse RDS")

    for name in ("get_by_sub", "find_conflicts", "update_profile", "insert"):
        monkeypatch.setattr(users, name, forbidden)
    return users


@pytest.mark.parametrize("bad", PATCH_CONTROL_VALUES.values(), ids=PATCH_CONTROL_VALUES.keys())
@pytest.mark.parametrize("template", ["Ana{}Editada", "Ana Editada{}"], ids=["middle", "trailing"])
def test_patch_me_rejects_control_characters_in_name(api, cognito, guarded_users, auth_header, template: str, bad: str) -> None:
    before = guarded_users.rows[COMPLETE_SUB]
    response = _patch_raw(api, auth_header, {"currentPassword": CURRENT, "fullName": template.format(bad)})
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert [f["field"] for f in body["details"]["fields"]] == ["fullName"]
    assert cognito.calls == []
    assert guarded_users.rows[COMPLETE_SUB] == before


@pytest.mark.parametrize("bad", ["\x00", "\ud800", "\udfff"], ids=["nul", "lone-high", "lone-low"])
def test_patch_me_rejects_nul_or_lone_surrogate_in_current_password(api, cognito, guarded_users, auth_header, bad: str) -> None:
    response = _patch_raw(api, auth_header, {"currentPassword": f"ClaveActual{bad}123!", "fullName": "Ana Editada"})
    body = assert_error(response, 400, "VALIDATION_ERROR")
    assert [f["field"] for f in body["details"]["fields"]] == ["currentPassword"]
    assert "ClaveActual" not in response.text
    assert cognito.calls == []


def test_patch_me_accepts_accents_enye_and_emoji(api, users, cognito, auth_header, fresh) -> None:
    name = "Ána Muñoz Güell 🌮✨"
    response = _patch_raw(api, auth_header, {"currentPassword": CURRENT, "fullName": name})
    assert response.status_code == 200, response.text
    assert response.json()["fullName"] == name
    assert users.rows[COMPLETE_SUB].full_name == name
    assert cognito.calls[-1] == ("update_attributes", {"access_token": fresh, "full_name": name, "dpi": None})
