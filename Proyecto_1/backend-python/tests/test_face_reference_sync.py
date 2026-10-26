"""complete-profile y PATCH /me escriben custom:face_reference_key en Cognito (mejor esfuerzo, PRO-14).

Con dobles: no demuestra que el rol real pueda ejecutar AdminUpdateUserAttributes (docs/api/python-face-login.md §6).
"""

from __future__ import annotations

import pytest

from app.common.errors import ApiError, ServiceUnavailableError
from app.modules.integrations.s3.objects import ObjectInfo
from tests.conftest import COMPLETE_SUB, INCOMPLETE_SUB, assert_error, running, seeded_users
from tests.fakes import FakeCognito, FakeImageObjects, tokens

ME = "/api/v1/me"
COMPLETE_PROFILE = "/api/v1/me/complete-profile"
CURRENT = "ClaveActual123!"
FILE = "0b6f6c4e-873e-486a-847e-aeaf52aa4e2e.jpg"
JPEG = ObjectInfo("image/jpeg", 120_000)
INCOMPLETE_PUBLIC = f"Fotos_Perfil/public/{INCOMPLETE_SUB}/{FILE}"
INCOMPLETE_REFERENCE = f"Fotos_Perfil/references/{INCOMPLETE_SUB}/{FILE}"
COMPLETE_PUBLIC = f"Fotos_Perfil/public/{COMPLETE_SUB}/{FILE}"
COMPLETE_REFERENCE = f"Fotos_Perfil/references/{COMPLETE_SUB}/{FILE}"


class SpyCognito(FakeCognito):
    """Anota qué guardaba RDS en el instante en que se escribe el atributo."""

    def __init__(self, users) -> None:
        super().__init__()
        self._users = users
        self.rds_at_sync: list[str | None] = []

    def update_face_reference(self, sub: str, reference_key: str) -> None:
        self.rds_at_sync.append(self._users.rows[sub].face_reference_key)
        super().update_face_reference(sub, reference_key)


@pytest.fixture
def users():
    return seeded_users()


@pytest.fixture
def cognito(users) -> SpyCognito:
    return SpyCognito(users)


@pytest.fixture
def images() -> FakeImageObjects:
    return FakeImageObjects(
        {
            INCOMPLETE_PUBLIC: JPEG,
            INCOMPLETE_REFERENCE: JPEG,
            COMPLETE_PUBLIC: JPEG,
            COMPLETE_REFERENCE: JPEG,
        }
    )


@pytest.fixture
def api(build_app, users, cognito, images):
    with running(build_app(users_repository=users, cognito_gateway=cognito, image_objects=images)) as client:
        yield client


def face_calls(cognito: FakeCognito) -> list[dict]:
    return [kw for name, kw in cognito.calls if name == "update_face_reference"]


def complete(api, auth_header, key: str = INCOMPLETE_PUBLIC, **extra):
    return api.post(COMPLETE_PROFILE, json={"profileImageKey": key, **extra}, headers=auth_header(INCOMPLETE_SUB))


def patch(api, auth_header, payload: dict):
    return api.patch(ME, json={"currentPassword": CURRENT, **payload}, headers=auth_header(COMPLETE_SUB))


# --- POST /me/complete-profile ---------------------------------------------------


def test_complete_profile_writes_reference_to_cognito_after_rds(api, users, cognito, auth_header) -> None:
    response = complete(api, auth_header)
    assert response.status_code == 200, response.text
    assert face_calls(cognito) == [{"sub": INCOMPLETE_SUB, "reference_key": INCOMPLETE_REFERENCE}]
    # La referencia ya estaba guardada en RDS cuando se escribió el atributo.
    assert cognito.rds_at_sync == [INCOMPLETE_REFERENCE]
    assert users.rows[INCOMPLETE_SUB].face_reference_key == INCOMPLETE_REFERENCE


def test_client_cannot_choose_the_reference_written_to_cognito(api, cognito, auth_header) -> None:
    other = f"Fotos_Perfil/references/{COMPLETE_SUB}/{FILE}"
    assert complete(api, auth_header, faceReferenceKey=other).status_code == 200
    assert [c["reference_key"] for c in face_calls(cognito)] == [INCOMPLETE_REFERENCE]


@pytest.mark.parametrize("error", [ServiceUnavailableError(), ApiError(429, "RATE_LIMITED")], ids=["503", "429"])
def test_complete_profile_survives_sync_failure(api, users, cognito, auth_header, log_stream, error) -> None:
    cognito.face_reference_errors = [error]
    response = complete(api, auth_header)
    assert response.status_code == 200, response.text
    assert response.json()["profileComplete"] is True
    assert users.rows[INCOMPLETE_SUB].face_reference_key == INCOMPLETE_REFERENCE
    logs = log_stream.getvalue()
    assert "face.reference_sync_failed" in logs and f'"reason": "{error.status_code}"' in logs
    # Ni la clave de S3 ni el sub aparecen en el evento.
    assert INCOMPLETE_REFERENCE not in logs and FILE not in logs


def test_success_is_logged_without_the_key(api, auth_header, log_stream) -> None:
    complete(api, auth_header)
    logs = log_stream.getvalue()
    assert "face.reference_synced" in logs and FILE not in logs


@pytest.mark.parametrize(
    "setup",
    ["missing-reference", "foreign-key", "already-complete"],
)
def test_no_sync_when_complete_profile_is_rejected(api, cognito, images, auth_header, setup: str) -> None:
    key = INCOMPLETE_PUBLIC
    sub_header = auth_header(INCOMPLETE_SUB)
    if setup == "missing-reference":
        del images.objects[INCOMPLETE_REFERENCE]
    elif setup == "foreign-key":
        key = COMPLETE_PUBLIC
    else:
        sub_header = auth_header(COMPLETE_SUB)
        key = COMPLETE_PUBLIC
    response = api.post(COMPLETE_PROFILE, json={"profileImageKey": key}, headers=sub_header)
    assert response.status_code in (400, 403, 409), response.text
    assert face_calls(cognito) == []


# --- PATCH /me -------------------------------------------------------------------


@pytest.fixture
def fresh(cognito, make_token) -> str:
    token = make_token(COMPLETE_SUB)
    cognito.auth_results = [tokens(token)]
    return token


def test_patch_with_new_photo_writes_new_reference(api, users, cognito, auth_header, fresh) -> None:
    new_file = "1c7f7d5f-984f-597f-958f-bfbf5fbf5f5f.jpg"
    public = f"Fotos_Perfil/public/{COMPLETE_SUB}/{new_file}"
    reference = f"Fotos_Perfil/references/{COMPLETE_SUB}/{new_file}"
    api.app.state.image_objects.objects.update({public: JPEG, reference: JPEG})
    response = patch(api, auth_header, {"profileImageKey": public})
    assert response.status_code == 200, response.text
    assert face_calls(cognito) == [{"sub": COMPLETE_SUB, "reference_key": reference}]
    assert cognito.rds_at_sync == [reference]


def test_patch_without_photo_does_not_touch_the_reference(api, cognito, auth_header, fresh) -> None:
    assert patch(api, auth_header, {"fullName": "Otro Nombre"}).status_code == 200
    assert face_calls(cognito) == []


def test_patch_with_same_photo_does_not_touch_the_reference(api, users, cognito, auth_header, fresh) -> None:
    current = users.rows[COMPLETE_SUB].profile_image_key
    assert patch(api, auth_header, {"profileImageKey": current}).status_code == 200
    assert face_calls(cognito) == []


def test_patch_survives_sync_failure(api, users, cognito, auth_header, fresh, log_stream) -> None:
    new_file = "1c7f7d5f-984f-597f-958f-bfbf5fbf5f5f.jpg"
    public = f"Fotos_Perfil/public/{COMPLETE_SUB}/{new_file}"
    api.app.state.image_objects.objects.update(
        {public: JPEG, f"Fotos_Perfil/references/{COMPLETE_SUB}/{new_file}": JPEG}
    )
    cognito.face_reference_errors = [ServiceUnavailableError()]
    response = patch(api, auth_header, {"profileImageKey": public})
    assert response.status_code == 200, response.text
    assert users.rows[COMPLETE_SUB].profile_image_key == public
    assert "face.reference_sync_failed" in log_stream.getvalue()


def test_patch_commit_failure_does_not_write_the_reference(api, users, cognito, auth_header, fresh) -> None:
    new_file = "1c7f7d5f-984f-597f-958f-bfbf5fbf5f5f.jpg"
    public = f"Fotos_Perfil/public/{COMPLETE_SUB}/{new_file}"
    api.app.state.image_objects.objects.update(
        {public: JPEG, f"Fotos_Perfil/references/{COMPLETE_SUB}/{new_file}": JPEG}
    )
    users.fail_commit = True
    assert_error(patch(api, auth_header, {"profileImageKey": public}), 503, "SERVICE_UNAVAILABLE")
    assert face_calls(cognito) == []
