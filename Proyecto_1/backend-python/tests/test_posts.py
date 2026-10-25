"""PRO-34: /posts, /posts/{postId}/comments y /labels (router + servicio + dobles).

Fixture A/B/C (mismos ids que backend-node/test/app.e2e-spec.ts y test_friends.py):
Ana (A) y Bruno (B) son amigos; Carla (C) no es amiga de ninguno; Dina (D) no tiene
foto de perfil. El SQL real se prueba con conexión falsa en test_posts_repository.py y
queda pendiente contra RDS, S3 y Rekognition reales (docs/api/python-posts.md §11).
"""

from __future__ import annotations

import re
import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from app.common.errors import ApiError
from app.main import _default_posts_repository
from app.modules.integrations.s3.objects import ObjectInfo
from app.modules.posts.repository import PostgresPostsRepository, UnavailablePostsRepository
from tests.conftest import FakeDatabase, assert_error, running
from tests.fakes import (
    CLOCK_START,
    FakeImageObjects,
    FakeLabelDetector,
    InMemoryFriendsRepository,
    InMemoryPostsRepository,
    InMemoryUsersRepository,
    label,
)

A_ID = "11111111-1111-4111-8111-111111111111"
B_ID = "22222222-2222-4222-8222-222222222222"
C_ID = "33333333-3333-4333-8333-333333333333"
D_ID = "44444444-4444-4444-8444-444444444444"
A_SUB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B_SUB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
C_SUB = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
D_SUB = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

API = "/api/v1"
BUCKET_URL = "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/"
CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
POST_KEYS = {"postId", "author", "imageUrl", "description", "labels", "commentsCount", "createdAt"}
COMMENT_KEYS = {"commentId", "author", "body", "createdAt"}
AWS_INTERNAL_MESSAGE = "arn:aws:iam::123456789012:role/internal no autorizado"


def _seed() -> InMemoryUsersRepository:
    users = InMemoryUsersRepository()
    users.add(A_SUB, email="ana@example.com", full_name="Ana López", dpi="1111111111111", complete=True, user_id=A_ID)
    users.add(B_SUB, email="bruno@example.com", full_name="Bruno Díaz", dpi="2222222222222", complete=True, user_id=B_ID)
    users.add(C_SUB, email="carla@example.com", full_name="Carla Ruiz", dpi="3333333333333", complete=True, user_id=C_ID)
    users.add(D_SUB, email="dina@example.com", full_name="Dina Pérez", dpi="4444444444444", complete=False, user_id=D_ID)
    return users


@pytest.fixture
def world(build_app):
    users = _seed()
    friends = InMemoryFriendsRepository(users)
    friends.friendships[(A_ID, B_ID)] = None  # A y B son amigos; C no
    posts = InMemoryPostsRepository(users, friends)
    images = FakeImageObjects()
    detector = FakeLabelDetector()
    app = build_app(
        users_repository=users,
        friends_repository=friends,
        posts_repository=posts,
        image_objects=images,
        label_detector=detector,
    )
    with running(app) as client:
        yield SimpleNamespace(client=client, users=users, friends=friends, posts=posts, images=images, detector=detector)


def upload(world, sub: str, *, ext: str = "jpg", content_type: str = "image/jpeg", labels=None) -> str:
    """Simula la Lambda de carga: deja el objeto en S3 y configura lo que detectará Rekognition."""
    key = f"Fotos_Publicadas/{sub}/{uuid.uuid4()}.{ext}"
    world.images.objects[key] = ObjectInfo(content_type=content_type, content_length=1024)
    world.detector.results[key] = labels if labels is not None else [label("perro", "98.12", "Dog")]
    return key


def publish(world, auth_header, sub: str, **fields: Any):
    key = fields.pop("imageKey", None) or upload(world, sub, labels=fields.pop("labels", None))
    return world.client.post(f"{API}/posts", json={"imageKey": key, **fields}, headers=auth_header(sub))


def feed(world, auth_header, sub: str, query: str = ""):
    return world.client.get(f"{API}/posts{query}", headers=auth_header(sub))


def post_ids(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [item["postId"] for item in response.json()["items"]]


# --- Criterio: crear publicación -----------------------------------------------------


def test_create_post_returns_contract_shape_and_persists(world, auth_header) -> None:
    key = upload(world, A_SUB, labels=[label("perro", "98.12", "Dog"), label("exterior", "91.44", "Outdoors")])
    response = world.client.post(
        f"{API}/posts", json={"imageKey": key, "description": "  Mi perro en el campus  "}, headers=auth_header(A_SUB)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == POST_KEYS
    UUID(body["postId"])
    assert body["author"] == {"userId": A_ID, "fullName": "Ana López", "profileImageUrl": body["author"]["profileImageUrl"]}
    assert body["author"]["profileImageUrl"].startswith(BUCKET_URL + "Fotos_Perfil/public/")
    assert body["imageUrl"] == BUCKET_URL + key
    assert body["description"] == "Mi perro en el campus"
    assert body["labels"] == ["perro", "exterior"]  # por confianza, solo nombres
    assert body["commentsCount"] == 0
    assert CREATED_AT_RE.match(body["createdAt"])
    assert world.detector.calls == [key]

    stored = world.posts.posts[body["postId"]]
    assert stored["author"] == A_ID and stored["image_key"] == key
    assert {name: (str(lb.confidence), lb.source_name) for name, lb in stored["labels"].items()} == {
        "perro": ("98.12", "Dog"),
        "exterior": ("91.44", "Outdoors"),
    }


def test_no_node_aliases_in_responses(world, auth_header) -> None:
    created = publish(world, auth_header, A_SUB).json()
    page = feed(world, auth_header, A_SUB).json()
    assert set(page) == {"items", "nextCursor"}  # sin "posts"
    assert set(page["items"][0]) == POST_KEYS == set(created)  # sin id, authorId, imageKey
    assert all(isinstance(name, str) for name in page["items"][0]["labels"])


def test_description_is_optional(world, auth_header) -> None:
    omitted = publish(world, auth_header, A_SUB)
    explicit_null = publish(world, auth_header, A_SUB, description=None)
    assert omitted.status_code == explicit_null.status_code == 201
    assert omitted.json()["description"] is None and explicit_null.json()["description"] is None


@pytest.mark.parametrize("description", ["", "   ", "\n\t "], ids=["vacía", "espacios", "solo blancos"])
def test_blank_description_is_400(world, auth_header, description: str) -> None:
    key = upload(world, A_SUB)
    response = world.client.post(f"{API}/posts", json={"imageKey": key, "description": description}, headers=auth_header(A_SUB))
    assert_error(response, 400, "VALIDATION_ERROR")
    assert world.detector.calls == [] and world.posts.posts == {}


def test_description_limit_is_2000_after_trim(world, auth_header) -> None:
    assert publish(world, auth_header, A_SUB, description="x" * 2000).status_code == 201
    assert_error(publish(world, auth_header, A_SUB, description="x" * 2001), 400, "VALIDATION_ERROR")


def test_description_keeps_newlines_but_rejects_nul(world, auth_header) -> None:
    assert publish(world, auth_header, A_SUB, description="línea 1\nlínea 2").json()["description"] == "línea 1\nlínea 2"
    assert_error(publish(world, auth_header, A_SUB, description="a\u0000b"), 400, "VALIDATION_ERROR")


@pytest.mark.parametrize("payload", [{}, {"description": "sin imagen"}, {"imageKey": ""}, {"imageKey": None}, {"imageKey": 7}])
def test_post_without_image_fails(world, auth_header, payload: dict[str, Any]) -> None:
    response = world.client.post(f"{API}/posts", json=payload, headers=auth_header(A_SUB))
    assert_error(response, 400, "VALIDATION_ERROR")
    assert world.detector.calls == [] and world.images.heads == [] and world.posts.posts == {}


@pytest.mark.parametrize(
    "key",
    [
        "Fotos_Perfil/public/{sub}/{uid}.jpg",  # prefijo de perfil
        "Fotos_Perfil/references/{sub}/{uid}.jpg",  # material privado de login facial
        "Fotos_Publicadas/{sub}/{uid}.gif",  # extensión que la Lambda no genera
        "Fotos_Publicadas/{sub}/campus.jpg",  # nombre que no es un UUID
        "Fotos_Publicadas/{sub}/sub/{uid}.jpg",  # ruta anidada
        "Fotos_Publicadas//{uid}.jpg",  # sub vacío
        "Fotos_Publicadas/{sub}/../{uid}.jpg",  # recorrido de rutas
        "fotos_publicadas/{sub}/{uid}.jpg",  # el prefijo distingue mayúsculas
        "Fotos_Publicadas/{sub}/{uid}.jpg\n",  # salto de línea final
    ],
)
def test_invalid_image_key_format_is_400(world, auth_header, key: str) -> None:
    key = key.format(sub=A_SUB, uid=uuid.uuid4())
    body = assert_error(
        world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB)), 400, "VALIDATION_ERROR"
    )
    assert body["details"] == {"reason": "INVALID_IMAGE_KEY"}
    assert world.images.heads == [] and world.detector.calls == []


def test_image_of_another_user_is_403_without_probing_s3(world, auth_header) -> None:
    key = upload(world, B_SUB)  # existe en S3, pero es de Bruno
    body = assert_error(
        world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB)), 403, "FORBIDDEN"
    )
    assert body["details"] == {"reason": "IMAGE_NOT_OWNED"}
    assert world.images.heads == [] and world.detector.calls == [] and world.posts.posts == {}


def test_missing_s3_object_is_404_and_not_analyzed(world, auth_header) -> None:
    key = f"Fotos_Publicadas/{A_SUB}/{uuid.uuid4()}.jpg"
    body = assert_error(
        world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB)), 404, "NOT_FOUND"
    )
    assert body["details"] == {"reason": "IMAGE_NOT_FOUND"}
    assert world.images.heads == [key] and world.detector.calls == [] and world.posts.posts == {}


def test_webp_is_rejected_because_rekognition_does_not_support_it(world, auth_header) -> None:
    key = upload(world, A_SUB, ext="webp", content_type="image/webp")
    body = assert_error(
        world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB)), 400, "VALIDATION_ERROR"
    )
    assert body["details"] == {"reason": "IMAGE_UNSUPPORTED"}
    assert world.detector.calls == [] and world.posts.posts == {}


def test_png_is_accepted(world, auth_header) -> None:
    key = upload(world, A_SUB, ext="png", content_type="image/png")
    assert world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB)).status_code == 201


def test_s3_failure_is_503_and_nothing_saved(world, auth_header) -> None:
    key = upload(world, A_SUB)
    world.images.error = ApiError(503, "SERVICE_UNAVAILABLE")
    assert_error(
        world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB)), 503, "SERVICE_UNAVAILABLE"
    )
    assert world.posts.posts == {}


# --- Rekognition: decisiones 1 y 2 -----------------------------------------------------


def test_no_labels_detected_saves_post_without_labels_not_general(world, auth_header) -> None:
    response = publish(world, auth_header, A_SUB, labels=[])
    assert response.status_code == 201, response.text
    assert response.json()["labels"] == []
    assert world.posts.posts[response.json()["postId"]]["labels"] == {}
    assert feed(world, auth_header, A_SUB).json()["items"][0]["labels"] == []
    assert world.client.get(f"{API}/labels", headers=auth_header(A_SUB)).json() == []  # sin "general"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ApiError(503, "SERVICE_UNAVAILABLE"), 503, "SERVICE_UNAVAILABLE"),
        (ApiError(429, "RATE_LIMITED"), 429, "RATE_LIMITED"),
        (ApiError(404, "NOT_FOUND", details={"reason": "IMAGE_NOT_FOUND"}), 404, "NOT_FOUND"),
        (ApiError(400, "VALIDATION_ERROR", details={"reason": "IMAGE_UNSUPPORTED"}), 400, "VALIDATION_ERROR"),
    ],
    ids=["503", "429", "404 InvalidS3Object", "400 formato"],
)
def test_rekognition_failure_saves_nothing(world, auth_header, error: ApiError, status: int, code: str) -> None:
    key = upload(world, A_SUB, labels=error)
    response = world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB))
    body = assert_error(response, status, code)
    assert AWS_INTERNAL_MESSAGE not in response.text
    assert world.posts.posts == {} and world.posts.comments == {}
    assert body["details"] in (None, error.details)
    assert feed(world, auth_header, A_SUB).json()["items"] == []


def test_database_failure_on_create_is_503_without_internal_message(world, auth_header) -> None:
    key = upload(world, A_SUB)
    world.posts.fail_with = ConnectionError("password=hunter2 host=rds.internal")
    response = world.client.post(f"{API}/posts", json={"imageKey": key}, headers=auth_header(A_SUB))
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert "hunter2" not in response.text and "rds.internal" not in response.text


# --- Criterio: A y B ven la publicación y C no --------------------------------------


def test_friends_see_post_and_stranger_does_not(world, auth_header) -> None:
    from_a = publish(world, auth_header, A_SUB, description="Hola desde el campus").json()
    from_b = publish(world, auth_header, B_SUB, labels=[label("gato", "97.50", "Cat")]).json()

    assert post_ids(feed(world, auth_header, A_SUB)) == [from_b["postId"], from_a["postId"]]  # más reciente primero
    assert post_ids(feed(world, auth_header, B_SUB)) == [from_b["postId"], from_a["postId"]]
    assert post_ids(feed(world, auth_header, C_SUB)) == []

    ana_item = next(i for i in feed(world, auth_header, B_SUB).json()["items"] if i["postId"] == from_a["postId"])
    assert ana_item["author"]["userId"] == A_ID and ana_item["description"] == "Hola desde el campus"


def test_stranger_sees_only_own_posts(world, auth_header) -> None:
    publish(world, auth_header, A_SUB)
    mine = publish(world, auth_header, C_SUB).json()
    assert post_ids(feed(world, auth_header, C_SUB)) == [mine["postId"]]
    assert mine["postId"] not in post_ids(feed(world, auth_header, A_SUB))


def test_friendship_made_later_exposes_existing_posts(world, auth_header) -> None:
    from_a = publish(world, auth_header, A_SUB).json()
    assert post_ids(feed(world, auth_header, C_SUB)) == []
    world.friends.friendships[(A_ID, C_ID)] = None
    assert post_ids(feed(world, auth_header, C_SUB)) == [from_a["postId"]]


# --- Criterio: orden y paginación estables --------------------------------------------


def _bulk(world, count: int, *, same_instant: bool = False) -> list[str]:
    instant = CLOCK_START
    ids = []
    for index in range(count):
        created = instant if same_instant else CLOCK_START + timedelta(seconds=index, microseconds=index)
        ids.append(world.posts.add_post(A_ID if index % 2 == 0 else B_ID, f"Fotos_Publicadas/x/{index}.jpg", created_at=created))
    return ids


def _walk(world, auth_header, sub: str, limit: int, query: str = "") -> list[str]:
    seen: list[str] = []
    cursor = None
    for _ in range(50):
        suffix = f"?limit={limit}" + (f"&cursor={cursor}" if cursor else "") + query
        page = feed(world, auth_header, sub, suffix)
        assert page.status_code == 200, page.text
        seen.extend(item["postId"] for item in page.json()["items"])
        cursor = page.json()["nextCursor"]
        if cursor is None:
            return seen
    raise AssertionError("la paginación no termina")


def test_pagination_covers_everything_in_descending_order_without_duplicates(world, auth_header) -> None:
    created = _bulk(world, 7)
    walked = _walk(world, auth_header, A_SUB, 3)
    assert walked == list(reversed(created))
    assert len(set(walked)) == 7


def test_pagination_is_stable_with_identical_created_at(world, auth_header) -> None:
    created = _bulk(world, 9, same_instant=True)
    walked = _walk(world, auth_header, B_SUB, 2)
    assert walked == sorted(created, reverse=True)  # desempate por id DESC
    assert len(set(walked)) == 9


def test_pagination_unaffected_by_new_post_between_pages(world, auth_header) -> None:
    created = _bulk(world, 5)
    first = feed(world, auth_header, A_SUB, "?limit=2").json()
    assert [i["postId"] for i in first["items"]] == [created[4], created[3]]
    publish(world, auth_header, A_SUB)  # publicación nueva entre páginas
    second = feed(world, auth_header, A_SUB, f"?limit=2&cursor={first['nextCursor']}").json()
    assert [i["postId"] for i in second["items"]] == [created[2], created[1]]


def test_last_page_has_null_cursor_and_exact_page_has_none_extra(world, auth_header) -> None:
    _bulk(world, 4)
    page = feed(world, auth_header, A_SUB, "?limit=4").json()
    assert len(page["items"]) == 4 and page["nextCursor"] is None
    assert feed(world, auth_header, A_SUB, "?limit=3").json()["nextCursor"] is not None


def test_default_limit_is_20_and_max_is_50(world, auth_header) -> None:
    _bulk(world, 55)
    assert len(feed(world, auth_header, A_SUB).json()["items"]) == 20
    assert len(feed(world, auth_header, A_SUB, "?limit=50").json()["items"]) == 50


@pytest.mark.parametrize("limit", ["0", "51", "-1", "abc", ""])
def test_limit_out_of_range_is_400(world, auth_header, limit: str) -> None:
    assert_error(feed(world, auth_header, A_SUB, f"?limit={limit}"), 400, "VALIDATION_ERROR")


@pytest.mark.parametrize("cursor", ["!!!", "bm9wZQ", "MjAyNi0xMC0yMFQxMjowMDowMFoj", "x" * 300])
def test_invalid_cursor_is_400_with_reason(world, auth_header, cursor: str) -> None:
    body = assert_error(feed(world, auth_header, A_SUB, f"?cursor={cursor}"), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_CURSOR"}


def test_cursor_is_the_common_cursor_of_pro15(world, auth_header) -> None:
    import base64

    _bulk(world, 3)
    cursor = feed(world, auth_header, A_SUB, "?limit=1").json()["nextCursor"]
    decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z#[0-9a-f-]{36}$", decoded)


# --- Filtro por etiqueta y buscador ------------------------------------------------------


def test_label_filter_returns_only_matching_posts(world, auth_header) -> None:
    dog = publish(world, auth_header, A_SUB, labels=[label("perro"), label("exterior")]).json()
    publish(world, auth_header, B_SUB, labels=[label("gato")])
    assert post_ids(feed(world, auth_header, B_SUB, "?label=perro")) == [dog["postId"]]
    assert post_ids(feed(world, auth_header, B_SUB, "?label=exterior")) == [dog["postId"]]
    assert post_ids(feed(world, auth_header, B_SUB, "?label=ciudad")) == []


@pytest.mark.parametrize("value", ["PERRO", "  perro  ", "Perro"])
def test_label_filter_is_trimmed_and_case_insensitive(world, auth_header, value: str) -> None:
    dog = publish(world, auth_header, A_SUB, labels=[label("perro")]).json()
    assert post_ids(feed(world, auth_header, A_SUB, f"?label={value}")) == [dog["postId"]]


def test_empty_label_means_no_filter(world, auth_header) -> None:
    publish(world, auth_header, A_SUB)
    assert len(post_ids(feed(world, auth_header, A_SUB, "?label="))) == 1
    assert len(post_ids(feed(world, auth_header, A_SUB, "?label=%20%20"))) == 1


def test_label_filter_does_not_leak_posts_of_strangers(world, auth_header) -> None:
    publish(world, auth_header, A_SUB, labels=[label("perro")])
    assert post_ids(feed(world, auth_header, C_SUB, "?label=perro")) == []


def test_label_filter_keeps_pagination(world, auth_header) -> None:
    ids = [publish(world, auth_header, A_SUB, labels=[label("perro")]).json()["postId"] for _ in range(5)]
    publish(world, auth_header, A_SUB, labels=[label("gato")])
    assert _walk(world, auth_header, A_SUB, 2, "&label=perro") == list(reversed(ids))


def test_label_filter_too_long_is_400(world, auth_header) -> None:
    body = assert_error(feed(world, auth_header, A_SUB, "?label=" + "a" * 101), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_LABEL"}


def test_labels_lists_visible_labels_with_counts(world, auth_header) -> None:
    publish(world, auth_header, A_SUB, labels=[label("perro"), label("exterior")])
    publish(world, auth_header, B_SUB, labels=[label("perro"), label("gato")])
    publish(world, auth_header, C_SUB, labels=[label("ciudad")])  # de una desconocida
    response = world.client.get(f"{API}/labels", headers=auth_header(A_SUB))
    assert response.status_code == 200
    assert response.json() == [
        {"name": "perro", "postCount": 2},
        {"name": "exterior", "postCount": 1},
        {"name": "gato", "postCount": 1},
    ]
    assert all(item["postCount"] >= 1 and set(item) == {"name", "postCount"} for item in response.json())
    assert "Todos" not in response.text
    assert world.client.get(f"{API}/labels", headers=auth_header(C_SUB)).json() == [{"name": "ciudad", "postCount": 1}]


def test_labels_search_by_name(world, auth_header) -> None:
    publish(world, auth_header, A_SUB, labels=[label("perro"), label("paisaje"), label("gato")])
    names = lambda q: [i["name"] for i in world.client.get(f"{API}/labels{q}", headers=auth_header(A_SUB)).json()]  # noqa: E731
    assert names("?q=pe") == ["perro"]
    assert names("?q=%20PA%20") == ["paisaje"]
    assert names("?q=") == ["gato", "paisaje", "perro"]
    assert names("?q=zzz") == []


def test_labels_query_too_long_is_400(world, auth_header) -> None:
    body = assert_error(
        world.client.get(f"{API}/labels?q={'a' * 101}", headers=auth_header(A_SUB)), 400, "VALIDATION_ERROR"
    )
    assert body["details"] == {"reason": "INVALID_QUERY"}


# --- Criterio: B comenta y C es rechazado; comentarios persistidos ---------------------------


def test_friend_can_comment_and_comment_is_persisted(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    path = f"{API}/posts/{post['postId']}/comments"
    created = world.client.post(path, json={"body": "  ¡Qué buena foto!  "}, headers=auth_header(B_SUB))
    assert created.status_code == 201, created.text
    comment = created.json()
    assert set(comment) == COMMENT_KEYS
    UUID(comment["commentId"])
    assert comment["body"] == "¡Qué buena foto!" and comment["author"]["userId"] == B_ID
    assert set(comment["author"]) == {"userId", "fullName", "profileImageUrl"}
    assert CREATED_AT_RE.match(comment["createdAt"])

    for sub in (A_SUB, B_SUB):  # lo ven el autor de la publicación y el amigo
        listed = world.client.get(path, headers=auth_header(sub))
        assert listed.status_code == 200
        assert [c["commentId"] for c in listed.json()] == [comment["commentId"]]
    assert feed(world, auth_header, A_SUB).json()["items"][0]["commentsCount"] == 1


def test_post_author_can_comment_own_post(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    response = world.client.post(f"{API}/posts/{post['postId']}/comments", json={"body": "Gracias"}, headers=auth_header(A_SUB))
    assert response.status_code == 201 and response.json()["author"]["userId"] == A_ID


def test_stranger_cannot_comment_or_read_and_gets_403(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    path = f"{API}/posts/{post['postId']}/comments"
    denied_post = world.client.post(path, json={"body": "hola"}, headers=auth_header(C_SUB))
    denied_get = world.client.get(path, headers=auth_header(C_SUB))
    for denied in (denied_post, denied_get):
        body = assert_error(denied, 403, "FORBIDDEN")
        assert body["details"] == {"reason": "NOT_FRIEND_OR_AUTHOR"}
    assert world.posts.comments[post["postId"]] == []

    # Una publicación inexistente sigue siendo 404 (sin details.reason).
    unknown = world.client.get(f"{API}/posts/{uuid.uuid4()}/comments", headers=auth_header(C_SUB))
    assert_error(unknown, 404, "NOT_FOUND")
    assert unknown.json()["details"] is None


def test_comment_on_missing_post_is_404(world, auth_header) -> None:
    path = f"{API}/posts/{uuid.uuid4()}/comments"
    assert_error(world.client.post(path, json={"body": "hola"}, headers=auth_header(A_SUB)), 404, "NOT_FOUND")
    assert_error(world.client.get(path, headers=auth_header(A_SUB)), 404, "NOT_FOUND")


@pytest.mark.parametrize("body", ["", "   ", "\n\t", None, 5], ids=["vacío", "espacios", "blancos", "null", "número"])
def test_blank_or_invalid_comment_is_400(world, auth_header, body: Any) -> None:
    post = publish(world, auth_header, A_SUB).json()
    response = world.client.post(f"{API}/posts/{post['postId']}/comments", json={"body": body}, headers=auth_header(B_SUB))
    assert_error(response, 400, "VALIDATION_ERROR")
    assert world.posts.comments[post["postId"]] == []


def test_comment_without_body_field_or_with_node_alias_is_400(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    path = f"{API}/posts/{post['postId']}/comments"
    assert_error(world.client.post(path, json={}, headers=auth_header(B_SUB)), 400, "VALIDATION_ERROR")
    # "content" es alias de Node; el contrato solo define "body".
    assert_error(world.client.post(path, json={"content": "hola"}, headers=auth_header(B_SUB)), 400, "VALIDATION_ERROR")


def test_comment_limit_is_1000(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    path = f"{API}/posts/{post['postId']}/comments"
    assert world.client.post(path, json={"body": "x" * 1000}, headers=auth_header(B_SUB)).status_code == 201
    assert_error(world.client.post(path, json={"body": "x" * 1001}, headers=auth_header(B_SUB)), 400, "VALIDATION_ERROR")


def test_comments_are_listed_chronologically(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    path = f"{API}/posts/{post['postId']}/comments"
    for sub, text in ((B_SUB, "primero"), (A_SUB, "segundo"), (B_SUB, "tercero")):
        assert world.client.post(path, json={"body": text}, headers=auth_header(sub)).status_code == 201
    listed = world.client.get(path, headers=auth_header(A_SUB)).json()
    assert [c["body"] for c in listed] == ["primero", "segundo", "tercero"]
    assert world.client.get(f"{API}/posts/{post['postId']}/comments", headers=auth_header(A_SUB)).json() == listed


def test_invalid_post_id_is_400(world, auth_header) -> None:
    assert_error(world.client.get(f"{API}/posts/no-es-uuid/comments", headers=auth_header(A_SUB)), 400, "VALIDATION_ERROR")
    assert_error(
        world.client.post(f"{API}/posts/no-es-uuid/comments", json={"body": "x"}, headers=auth_header(A_SUB)),
        400,
        "VALIDATION_ERROR",
    )


# --- Autenticación y perfil ---------------------------------------------------------------------


ROUTES = [
    ("get", "/posts", None),
    ("post", "/posts", {"imageKey": "Fotos_Publicadas/x/y.jpg"}),
    ("get", f"/posts/{uuid.uuid4()}/comments", None),
    ("post", f"/posts/{uuid.uuid4()}/comments", {"body": "hola"}),
    ("get", "/labels", None),
]


@pytest.mark.parametrize(("method", "path", "payload"), ROUTES)
def test_requires_authentication(world, method: str, path: str, payload: Any) -> None:
    assert_error(getattr(world.client, method)(f"{API}{path}", **({"json": payload} if payload else {})), 401, "UNAUTHENTICATED")


@pytest.mark.parametrize(("method", "path", "payload"), ROUTES)
def test_incomplete_profile_is_403_before_anything_else(world, auth_header, method: str, path: str, payload: Any) -> None:
    kwargs = {"json": payload} if payload else {}
    body = assert_error(getattr(world.client, method)(f"{API}{path}", headers=auth_header(D_SUB), **kwargs), 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}
    assert world.detector.calls == [] and world.images.heads == []


# --- RDS ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "payload"), [r for r in ROUTES if "comments" not in r[1]])
def test_database_failure_is_503_without_internal_message(world, auth_header, method: str, path: str, payload: Any) -> None:
    key = upload(world, A_SUB)
    payload = {"imageKey": key} if payload else None
    world.posts.fail_with = ConnectionError("password=hunter2 host=rds.internal")
    kwargs = {"json": payload} if payload else {}
    response = getattr(world.client, method)(f"{API}{path}", headers=auth_header(A_SUB), **kwargs)
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert "hunter2" not in response.text and "rds.internal" not in response.text


def test_database_failure_on_comments_is_503(world, auth_header) -> None:
    post = publish(world, auth_header, A_SUB).json()
    world.posts.fail_with = ConnectionError("rds.internal")
    path = f"{API}/posts/{post['postId']}/comments"
    assert_error(world.client.get(path, headers=auth_header(A_SUB)), 503, "SERVICE_UNAVAILABLE")
    assert_error(world.client.post(path, json={"body": "hola"}, headers=auth_header(A_SUB)), 503, "SERVICE_UNAVAILABLE")


def test_profile_lookup_failure_is_503(world, auth_header) -> None:
    world.users.fail_with = ConnectionError("db caída")
    assert_error(feed(world, auth_header, A_SUB), 503, "SERVICE_UNAVAILABLE")


def test_without_rds_there_is_no_memory_fallback() -> None:
    assert isinstance(_default_posts_repository(FakeDatabase(configured=False)), UnavailablePostsRepository)
    assert isinstance(_default_posts_repository(FakeDatabase(configured=True)), PostgresPostsRepository)
    unavailable = UnavailablePostsRepository()
    calls = (
        lambda: unavailable.list_feed(A_ID, None, None, 20),
        lambda: unavailable.create_post(A_ID, "k", None, []),
        lambda: unavailable.list_labels(A_ID, None),
        lambda: unavailable.list_comments(A_ID, B_ID),
        lambda: unavailable.create_comment(A_ID, B_ID, "x"),
    )
    for call in calls:
        with pytest.raises(ApiError) as caught:
            call()
        assert caught.value.status_code == 503


def test_default_app_without_rds_answers_503(public_pem, auth_header) -> None:
    from app.common.auth import CognitoTokenVerifier, static_key_resolver
    from app.main import create_app
    from tests.conftest import ISSUER, CLIENT_ID, local_settings

    users = _seed()
    app = create_app(
        local_settings(),
        database=FakeDatabase(configured=False),
        verifier=CognitoTokenVerifier(ISSUER, CLIENT_ID, static_key_resolver(public_pem)),
        users_repository=users,
        friends_repository=InMemoryFriendsRepository(users),
        image_objects=FakeImageObjects(),
        label_detector=FakeLabelDetector(),
    )
    with running(app) as client:
        for path in ("/posts", "/labels"):
            assert_error(client.get(f"{API}{path}", headers=auth_header(A_SUB)), 503, "SERVICE_UNAVAILABLE")
    assert isinstance(app.state.posts_repository, UnavailablePostsRepository)


# --- Logs sin PII ---------------------------------------------------------------------------------


def test_logs_do_not_contain_texts_keys_or_labels(world, auth_header, log_stream) -> None:
    key = upload(world, A_SUB, labels=[label("perro", "98.12", "Dog")])
    created = world.client.post(
        f"{API}/posts", json={"imageKey": key, "description": "descripción-secreta-123"}, headers=auth_header(A_SUB)
    ).json()
    world.client.post(
        f"{API}/posts/{created['postId']}/comments", json={"body": "comentario-secreto-456"}, headers=auth_header(B_SUB)
    )
    world.posts.fail_with = ConnectionError("password=hunter2")
    world.client.get(f"{API}/posts", headers=auth_header(A_SUB))
    output = log_stream.getvalue()
    assert '"event": "posts.created"' in output and '"labelCount": 1' in output
    assert '"event": "posts.db_error"' in output and '"errorType": "ConnectionError"' in output
    for secret in ("descripción-secreta-123", "comentario-secreto-456", key, A_SUB, "hunter2", "perro"):
        assert secret not in output
