"""GET /api/v1/conversations/{friendId}/messages (PRO-16): historial paginado, igual que Node."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.modules.social.cursor import encode_cursor
from tests.chat_world import A_ID, A_SUB, B_ID, B_SUB, C_ID, C_SUB, D_SUB, make_world
from tests.conftest import assert_error

ISO_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
MESSAGE_KEYS = {"messageId", "senderId", "recipientId", "body", "createdAt", "readAt"}


@pytest.fixture
def world(build_app):
    return make_world(build_app)


@pytest.fixture
def client(world):
    with TestClient(world.apps[0]) as test_client:
        yield test_client


def seed(world, count: int) -> list[str]:
    """Mensajes A→B / B→A alternados; devuelve sus cuerpos en orden cronológico."""
    bodies = []
    for n in range(count):
        sender, recipient = (A_ID, B_ID) if n % 2 == 0 else (B_ID, A_ID)
        world.repo.insert_message(sender, recipient, f"mensaje {n}", None)
        bodies.append(f"mensaje {n}")
    return bodies


def history(client, auth_header, friend=B_ID, sub=A_SUB, query=""):
    return client.get(f"/api/v1/conversations/{friend}/messages{query}", headers=auth_header(sub))


def test_returns_conversation_in_ascending_order_with_contract_shape(world, client, auth_header) -> None:
    bodies = seed(world, 4)
    response = history(client, auth_header)
    assert response.status_code == 200
    page = response.json()
    assert set(page) == {"items", "nextCursor"} and page["nextCursor"] is None
    assert [m["body"] for m in page["items"]] == bodies  # cronológico ascendente, como Node
    assert all(set(m) == MESSAGE_KEYS and ISO_MS.match(m["createdAt"]) and m["readAt"] is None for m in page["items"])
    assert page["items"][0]["senderId"] == A_ID and page["items"][1]["senderId"] == B_ID


def test_both_participants_see_the_same_conversation(world, client, auth_header) -> None:
    seed(world, 3)
    assert history(client, auth_header, A_ID, B_SUB).json() == history(client, auth_header, B_ID, A_SUB).json()


def test_empty_conversation(client, auth_header) -> None:
    assert history(client, auth_header).json() == {"items": [], "nextCursor": None}


def test_pagination_walks_backwards_with_node_style_cursor(world, client, auth_header) -> None:
    bodies = seed(world, 5)
    first = history(client, auth_header, query="?limit=2").json()
    assert [m["body"] for m in first["items"]] == bodies[3:]
    # Como Node: nextCursor es el createdAt (ISO, ms) del mensaje MÁS ANTIGUO de la página.
    assert first["nextCursor"] == first["items"][0]["createdAt"]

    second = history(client, auth_header, query=f"?limit=2&cursor={first['nextCursor']}").json()
    assert [m["body"] for m in second["items"]] == bodies[1:3]
    third = history(client, auth_header, query=f"?limit=2&cursor={second['nextCursor']}").json()
    assert [m["body"] for m in third["items"]] == bodies[:1] and third["nextCursor"] is None


def test_page_exactly_full_has_no_next_cursor(world, client, auth_header) -> None:
    seed(world, 4)
    page = history(client, auth_header, query="?limit=4").json()
    assert len(page["items"]) == 4 and page["nextCursor"] is None


def test_default_limit_is_50_like_node(world, client, auth_header) -> None:
    seed(world, 60)
    page = history(client, auth_header).json()
    assert len(page["items"]) == 50 and page["nextCursor"] == page["items"][0]["createdAt"]


def test_common_cursor_format_is_also_accepted(world, client, auth_header) -> None:
    bodies = seed(world, 3)
    newest = world.repo.rows[-1]
    cursor = encode_cursor(newest.created_at[:-1] + "000Z", newest.id)  # 6 decimales, formato de social/cursor.py
    page = history(client, auth_header, query=f"?cursor={cursor}").json()
    assert [m["body"] for m in page["items"]] == bodies[:2]


@pytest.mark.parametrize("cursor", ["no-es-un-cursor", "2026-10-26", "2026-10-26T12:00:00+00:00", "%25%25", "a" * 300])
def test_invalid_cursor_is_400(client, auth_header, cursor) -> None:
    body = assert_error(history(client, auth_header, query=f"?cursor={cursor}"), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_CURSOR"}


@pytest.mark.parametrize("limit", ["0", "51", "-1", "x"])
def test_invalid_limit_is_400(client, auth_header, limit) -> None:
    assert_error(history(client, auth_header, query=f"?limit={limit}"), 400, "VALIDATION_ERROR")


def test_only_the_requested_conversation_is_returned(world, client, auth_header) -> None:
    world.friends.friendships[(A_ID, C_ID)] = None
    world.repo.insert_message(A_ID, B_ID, "con Bruno", None)
    world.repo.insert_message(A_ID, C_ID, "con Carla", None)
    assert [m["body"] for m in history(client, auth_header).json()["items"]] == ["con Bruno"]
    assert [m["body"] for m in history(client, auth_header, C_ID).json()["items"]] == ["con Carla"]


def test_unauthenticated_is_401(client) -> None:
    assert_error(client.get(f"/api/v1/conversations/{B_ID}/messages"), 401, "UNAUTHENTICATED")


def test_incomplete_profile_is_403(client, auth_header) -> None:
    body = assert_error(history(client, auth_header, sub=D_SUB), 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}


def test_not_friends_is_403(world, client, auth_header) -> None:
    body = assert_error(history(client, auth_header, C_ID), 403, "FORBIDDEN")
    assert body["details"] == {"reason": "NOT_FRIENDS"}
    assert_error(history(client, auth_header, A_ID), 403, "FORBIDDEN")  # uno mismo


def test_unknown_friend_is_404(client, auth_header) -> None:
    assert_error(history(client, auth_header, "00000000-0000-4000-8000-000000000000"), 404, "NOT_FOUND")


def test_malformed_friend_id_is_400(client, auth_header) -> None:
    assert_error(history(client, auth_header, "no-es-uuid"), 400, "VALIDATION_ERROR")


def test_rds_failure_is_503_without_leaking_details(world, client, auth_header) -> None:
    world.repo.fail_with = ConnectionError("password=hunter2 host=rds.internal")
    response = history(client, auth_header)
    body = assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert "hunter2" not in response.text and "rds.internal" not in response.text
    assert body["details"] is None


def test_user_lookup_failure_is_503(world, client, auth_header) -> None:
    world.users.fail_with = ConnectionError("rds caído")
    assert history(client, auth_header, query="?cursor=2026-10-26T12:00:00.000Z").status_code == 503
