"""WebSocket /ws/chat (PRO-16) con el cliente de pruebas de Starlette.

Cubre handshake, códigos de cierre (iguales a Node), validaciones, entrega local,
difusión entre DOS aplicaciones que comparten un bus que imita LISTEN/NOTIFY, y
los casos negativos. El SQL real y el ALB quedan pendientes de RDS (python-chat.md §10).
"""

from __future__ import annotations

import json
import time
from contextlib import ExitStack, contextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

from app.modules.chat.websocket import MAX_FRAME_BYTES
from tests.chat_world import (
    A_ID,
    A_SUB,
    B_ID,
    B_SUB,
    C_ID,
    C_SUB,
    CLIENT_MESSAGE_ID,
    D_SUB,
    GHOST_SUB,
    make_world,
    send_frame,
    wait_ready,
    wait_until,
    ws_url,
)
from tests.conftest import FakeDatabase


@pytest.fixture
def world(build_app):
    return make_world(build_app)


@pytest.fixture
def client(world):
    with TestClient(world.apps[0]) as test_client:
        wait_ready(world.apps[0])
        yield test_client


def close_of(client: TestClient, url: str) -> WebSocketDisconnect:
    """Abre el socket y devuelve el cierre que el servidor envía tras aceptar."""
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect(url) as ws:
            ws.receive_json()
    return closed.value


# --- handshake: autorización y códigos de cierre -------------------------------------


def test_connect_sends_connected_and_ping_pong(client, make_token) -> None:
    with client.websocket_connect(ws_url(make_token(A_SUB), B_ID)) as ws:
        assert ws.receive_json() == {"event": "connected", "data": {"userId": A_ID, "friendId": B_ID}}
        ws.send_json({"event": "ping"})
        assert ws.receive_json() == {"event": "pong"}


def test_alias_path_matches_node(client, make_token) -> None:
    with client.websocket_connect(ws_url(make_token(A_SUB), B_ID, "/api/v1/chat/ws")) as ws:
        assert ws.receive_json()["event"] == "connected"


def test_missing_token_is_4401(client) -> None:
    closed = close_of(client, ws_url(None, B_ID))
    assert (closed.code, closed.reason) == (4401, "Unauthorized: token is required")


def test_empty_token_is_4401(client) -> None:
    assert close_of(client, ws_url("", B_ID)).code == 4401


def test_missing_friend_id_is_4400(client, make_token) -> None:
    closed = close_of(client, ws_url(make_token(A_SUB), None))
    assert (closed.code, closed.reason) == (4400, "Bad Request: friendId is required")


def test_token_check_comes_before_friend_id(client) -> None:
    assert close_of(client, ws_url(None, None)).code == 4401


@pytest.mark.parametrize(
    "overrides",
    [{"exp": int(time.time()) - 60}, {"client_id": "otro-cliente"}, {"token_use": "id"}, {"iss": "https://evil.example"}],
    ids=["expired", "wrong-client", "id-token", "wrong-issuer"],
)
def test_invalid_tokens_are_4401(client, make_token, overrides) -> None:
    closed = close_of(client, ws_url(make_token(A_SUB, **overrides), B_ID))
    assert (closed.code, closed.reason) == (4401, "Unauthorized: invalid token")


def test_garbage_and_foreign_key_tokens_are_4401(client, make_token) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert close_of(client, ws_url("no.es.un-jwt", B_ID)).code == 4401
    assert close_of(client, ws_url(make_token(A_SUB, key=foreign), B_ID)).code == 4401


def test_valid_token_without_user_row_is_4401(client, make_token) -> None:
    assert close_of(client, ws_url(make_token(GHOST_SUB), B_ID)).code == 4401


def test_incomplete_profile_is_4403(client, make_token) -> None:
    closed = close_of(client, ws_url(make_token(D_SUB), B_ID))
    assert (closed.code, closed.reason) == (4403, "Forbidden: PROFILE_INCOMPLETE")


@pytest.mark.parametrize(
    "friend",
    [C_ID, A_ID, "00000000-0000-4000-8000-000000000000", "no-es-uuid"],
    ids=["not-friend", "self", "unknown", "malformed"],
)
def test_not_friends_is_4403(client, make_token, friend) -> None:
    closed = close_of(client, ws_url(make_token(A_SUB), friend))
    assert (closed.code, closed.reason) == (4403, "Forbidden: NOT_FRIENDS")


def test_rds_failure_during_handshake_is_1011(world, client, make_token) -> None:
    world.users.fail_with = ConnectionError("rds caído")
    closed = close_of(client, ws_url(make_token(A_SUB), B_ID))
    assert (closed.code, closed.reason) == (1011, "Internal Error")


def test_friendship_lookup_failure_is_1011(world, client, make_token) -> None:
    world.repo.fail_with = ConnectionError("rds caído")
    assert close_of(client, ws_url(make_token(A_SUB), B_ID)).code == 1011


# --- sin RDS: 503 antes del upgrade, sin respaldo en memoria --------------------------------


def test_without_database_the_handshake_is_503(build_app, make_token) -> None:
    app = build_app(database=FakeDatabase(configured=False))
    with TestClient(app) as client:
        assert app.state.chat_listener is None  # LISTEN solo se inicia con RDS configurado
        with pytest.raises(WebSocketDenialResponse) as denied:
            with client.websocket_connect(ws_url(make_token(A_SUB), B_ID)):
                pass
    assert denied.value.status_code == 503
    assert denied.value.json()["code"] == "SERVICE_UNAVAILABLE"


def test_without_database_history_is_503_and_nothing_is_stored(build_app, auth_header) -> None:
    from app.modules.chat.repository import UnavailableChatRepository

    users_world = make_world(build_app)
    app = build_app(
        database=FakeDatabase(configured=False),
        users_repository=users_world.users,
        friends_repository=users_world.friends,
        chat_repository=UnavailableChatRepository(),
    )
    with TestClient(app) as client:
        response = client.get(f"/api/v1/conversations/{B_ID}/messages", headers=auth_header(A_SUB))
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"


def test_default_chat_repository_without_database_is_unavailable(build_app) -> None:
    from app.main import _default_chat_repository
    from app.modules.chat.repository import PostgresChatRepository, UnavailableChatRepository

    assert isinstance(_default_chat_repository(FakeDatabase(configured=False)), UnavailableChatRepository)
    assert isinstance(_default_chat_repository(FakeDatabase(configured=True)), PostgresChatRepository)


def test_listener_down_rejects_new_connections_with_503(world, client, make_token) -> None:
    world.bus.drop_connections()
    world.bus.fail_connects = 10_000
    wait_until(lambda: not world.apps[0].state.chat_listener.ready)
    with pytest.raises(WebSocketDenialResponse) as denied:
        with client.websocket_connect(ws_url(make_token(A_SUB), B_ID)):
            pass
    assert denied.value.status_code == 503


# --- envío: validaciones (sin tumbar la conexión) -----------------------------------------


@contextmanager
def connected(client, make_token, sub=A_SUB, friend=B_ID):
    with client.websocket_connect(ws_url(make_token(sub), friend)) as session:
        assert session.receive_json()["event"] == "connected"
        yield session


@pytest.mark.parametrize(
    "body",
    ["", "   ", "\n\t ", "x" * 4001, "  " + "x" * 4001 + "  ", None, 123, ["hola"], "hola\x00mundo", "\ud800"],
    ids=["empty", "spaces", "whitespace", "4001", "4001-padded", "null", "number", "list", "nul", "surrogate"],
)
def test_invalid_body_is_validation_error_and_connection_survives(world, client, make_token, body) -> None:
    with connected(client, make_token) as session:
        session.send_text(json.dumps(send_frame(B_ID, body)))
        error = session.receive_json()
        assert error["event"] == "error"
        assert error["data"]["code"] == "VALIDATION_ERROR"
        assert error["data"]["clientMessageId"] == CLIENT_MESSAGE_ID
        session.send_json({"event": "ping"})
        assert session.receive_json() == {"event": "pong"}
    assert world.repo.rows == []


def test_body_of_exactly_4000_characters_is_accepted(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        session.send_json(send_frame(B_ID, "x" * 4000))
        ack = session.receive_json()
    assert ack["event"] == "message:ack"
    assert len(ack["data"]["body"]) == 4000


def test_body_is_trimmed(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        session.send_json(send_frame(B_ID, "   hola   "))
        assert session.receive_json()["data"]["body"] == "hola"


def test_recipient_must_match_the_conversation(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        for recipient in (C_ID, None, A_ID):
            frame = send_frame(B_ID, "hola")
            frame["data"]["recipientId"] = recipient
            session.send_json(frame)
            error = session.receive_json()
            assert error["data"]["code"] == "VALIDATION_ERROR"
            assert "recipientId" in error["data"]["message"]
    assert world.repo.rows == []


def test_invalid_json_and_unknown_events(client, make_token) -> None:
    with connected(client, make_token) as session:
        session.send_text("{no es json")
        error = session.receive_json()
        assert error["data"]["code"] == "VALIDATION_ERROR"
        assert "clientMessageId" not in error["data"]
        for ignored in ('"texto"', "[1,2]", "null", '{"event":"desconocido"}', '{"event":"message:new"}'):
            session.send_text(ignored)  # Node descarta los eventos desconocidos sin responder
        session.send_json({"event": "ping"})
        assert session.receive_json() == {"event": "pong"}


def test_message_send_without_data_is_validation_error(client, make_token) -> None:
    with connected(client, make_token) as session:
        session.send_json({"event": "message:send"})
        assert session.receive_json()["data"]["code"] == "VALIDATION_ERROR"


def test_client_cannot_spoof_the_sender(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        frame = send_frame(B_ID, "hola")
        frame["data"]["senderId"] = C_ID
        session.send_json(frame)
        ack = session.receive_json()
    assert ack["data"]["senderId"] == A_ID
    assert world.repo.rows[0].sender_id == A_ID


def test_message_too_big_closes_with_1009(client, make_token) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with connected(client, make_token) as session:
            session.send_text("x" * (MAX_FRAME_BYTES + 1))
            session.receive_json()
    assert closed.value.code == 1009


def test_notify_payload_over_postgres_limit_is_rejected_not_lost(world, client, make_token) -> None:
    # 4000 emojis = 16 KB en UTF-8: cabe en la columna pero no en un NOTIFY (< 8000 bytes).
    with connected(client, make_token) as session:
        session.send_json(send_frame(B_ID, "😀" * 4000))
        error = session.receive_json()
        assert error["data"]["code"] == "VALIDATION_ERROR"
        assert "difundirse" in error["data"]["message"]
    assert world.repo.rows == [] and world.bus.published == []


def test_rds_failure_while_sending_is_internal_error(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        world.repo.fail_with = ConnectionError("rds caído: password=hunter2")
        session.send_json(send_frame(B_ID, "hola"))
        error = session.receive_json()
        assert error == {
            "event": "error",
            "data": {"code": "INTERNAL_ERROR", "message": "Error al persistir el mensaje.", "clientMessageId": CLIENT_MESSAGE_ID},
        }
        world.repo.fail_with = None
        session.send_json({"event": "ping"})
        assert session.receive_json() == {"event": "pong"}


def test_friendship_removed_after_connect_is_forbidden(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        del world.friends.friendships[(A_ID, B_ID)]
        session.send_json(send_frame(B_ID, "hola"))
        error = session.receive_json()
    assert error["data"]["code"] == "FORBIDDEN"
    assert world.repo.rows == [] and world.bus.published == []


def test_send_is_rejected_when_listener_is_down(world, client, make_token) -> None:
    with connected(client, make_token) as session:
        world.bus.drop_connections()
        world.bus.fail_connects = 10_000
        wait_until(lambda: not world.apps[0].state.chat_listener.ready)
        session.send_json(send_frame(B_ID, "hola"))
        error = session.receive_json()
    assert error["data"]["code"] == "SERVICE_UNAVAILABLE"
    assert error["data"]["clientMessageId"] == CLIENT_MESSAGE_ID
    assert world.repo.rows == []  # no se guarda lo que nadie podría confirmar


# --- entrega local y aislamiento -----------------------------------------------------------


def test_same_instance_ack_and_new(world, client, make_token) -> None:
    with ExitStack() as stack:
        a = stack.enter_context(client.websocket_connect(ws_url(make_token(A_SUB), B_ID)))
        b = stack.enter_context(client.websocket_connect(ws_url(make_token(B_SUB), A_ID)))
        a.receive_json(), b.receive_json()

        a.send_json(send_frame(B_ID, "Hola Bruno"))
        ack, new = a.receive_json(), b.receive_json()

    stored = world.repo.rows[0]
    assert ack == {
        "event": "message:ack",
        "data": {
            "clientMessageId": CLIENT_MESSAGE_ID,
            "messageId": stored.id,
            "senderId": A_ID,
            "recipientId": B_ID,
            "body": "Hola Bruno",
            "createdAt": stored.created_at,
        },
    }
    assert new == {
        "event": "message:new",
        "data": {
            "messageId": stored.id,
            "senderId": A_ID,
            "recipientId": B_ID,
            "body": "Hola Bruno",
            "createdAt": stored.created_at,
            "readAt": None,
        },
    }
    assert stored.created_at.endswith("Z") and len(stored.created_at) == 24  # ISO con milisegundos


def test_ack_without_client_message_id_omits_the_field(client, make_token) -> None:
    with connected(client, make_token) as session:
        session.send_json(send_frame(B_ID, "hola", client_message_id=None))
        assert "clientMessageId" not in session.receive_json()["data"]


def test_delivery_only_reaches_sockets_of_that_conversation(world, client, make_token) -> None:
    world.friends.friendships[(A_ID, C_ID)] = None
    with ExitStack() as stack:
        a_with_b = stack.enter_context(client.websocket_connect(ws_url(make_token(A_SUB), B_ID)))
        a_with_c = stack.enter_context(client.websocket_connect(ws_url(make_token(A_SUB), C_ID)))
        b = stack.enter_context(client.websocket_connect(ws_url(make_token(B_SUB), A_ID)))
        c = stack.enter_context(client.websocket_connect(ws_url(make_token(C_SUB), A_ID)))
        for ws in (a_with_b, a_with_c, b, c):
            ws.receive_json()

        b.send_json(send_frame(A_ID, "para Ana"))
        assert b.receive_json()["event"] == "message:ack"
        assert a_with_b.receive_json()["event"] == "message:new"
        # Ni el socket de A con C ni el de C reciben nada de la conversación A-B.
        for other in (a_with_c, c):
            other.send_json({"event": "ping"})
            assert other.receive_json() == {"event": "pong"}


def test_hub_forgets_disconnected_sockets(world, client, make_token) -> None:
    hub = world.apps[0].state.chat_hub
    with client.websocket_connect(ws_url(make_token(A_SUB), B_ID)) as ws:
        ws.receive_json()
        assert hub.connection_count == 1
    wait_until(lambda: hub.connection_count == 0)


# --- difusión entre DOS instancias (EC2 Node/Python sobre un RDS) -----------------------------


def test_cross_instance_broadcast_both_directions(build_app, make_token) -> None:
    world = make_world(build_app, instances=2)
    app1, app2 = world.apps
    with TestClient(app1) as c1, TestClient(app2) as c2:
        wait_ready(app1), wait_ready(app2)
        with c1.websocket_connect(ws_url(make_token(A_SUB), B_ID)) as a, c2.websocket_connect(
            ws_url(make_token(B_SUB), A_ID)
        ) as b:
            a.receive_json(), b.receive_json()

            a.send_json(send_frame(B_ID, "de A en la instancia 1"))
            new = b.receive_json()
            assert new["event"] == "message:new" and new["data"]["body"] == "de A en la instancia 1"
            assert a.receive_json()["event"] == "message:ack"

            reply_id = "d4a3b2a1-0000-4000-8000-111122223333"
            b.send_json(send_frame(A_ID, "de B en la instancia 2", reply_id))
            back = a.receive_json()
            assert back["event"] == "message:new" and back["data"]["body"] == "de B en la instancia 2"
            ack = b.receive_json()
            assert ack["event"] == "message:ack" and ack["data"]["clientMessageId"] == reply_id

    assert [m.body for m in world.repo.rows] == ["de A en la instancia 1", "de B en la instancia 2"]
    assert len(world.bus.published) == 2


def test_messages_keep_their_order_across_instances(build_app, make_token) -> None:
    world = make_world(build_app, instances=2)
    app1, app2 = world.apps
    with TestClient(app1) as c1, TestClient(app2) as c2:
        wait_ready(app1), wait_ready(app2)
        with c1.websocket_connect(ws_url(make_token(A_SUB), B_ID)) as a, c2.websocket_connect(
            ws_url(make_token(B_SUB), A_ID)
        ) as b:
            a.receive_json(), b.receive_json()
            for n in range(20):
                a.send_json(send_frame(B_ID, f"mensaje {n}", f"00000000-0000-4000-8000-{n:012d}"))
            received = [b.receive_json()["data"]["body"] for _ in range(20)]
    assert received == [f"mensaje {n}" for n in range(20)]


def test_notification_from_node_with_extra_or_missing_fields(world, client, make_token) -> None:
    """Un NOTIFY publicado por Node (sin clientMessageId) llega como message:new y no rompe el hub."""
    with client.websocket_connect(ws_url(make_token(B_SUB), A_ID)) as b:
        b.receive_json()
        world.bus.publish("esto no es json")
        world.bus.publish(json.dumps({"messageId": 5}))
        world.bus.publish(
            json.dumps(
                {
                    "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                    "senderId": A_ID,
                    "recipientId": B_ID,
                    "body": "desde Node",
                    "createdAt": "2026-10-26T12:00:00.000Z",
                }
            )
        )
        frame = b.receive_json()
    assert frame["event"] == "message:new"
    assert frame["data"] == {
        "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "senderId": A_ID,
        "recipientId": B_ID,
        "body": "desde Node",
        "createdAt": "2026-10-26T12:00:00.000Z",
        "readAt": None,
    }


# --- el token y el contenido no aparecen en los logs -------------------------------------------


def test_logs_never_contain_token_friend_or_content(world, client, make_token, log_stream) -> None:
    token = make_token(A_SUB)
    secret = "contenido-secreto-9f3a"
    with client.websocket_connect(ws_url(token, B_ID)) as ws:
        ws.receive_json()
        ws.send_json(send_frame(B_ID, secret))
        ws.receive_json()
        ws.send_text("{roto " + secret)
        ws.receive_json()
    close_of(client, ws_url(token, C_ID))  # rechazo por no ser amigos
    world.repo.fail_with = ConnectionError(f"rds caído password=hunter2 {secret}")
    assert close_of(client, ws_url(token, B_ID)).code == 1011  # RDS caído en el handshake
    logs = log_stream.getvalue()
    for forbidden in (token, token.split(".")[1], secret, "hunter2", f"token={token[:10]}"):
        assert forbidden not in logs
