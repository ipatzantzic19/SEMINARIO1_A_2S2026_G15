"""Escenario común de las pruebas del chat (PRO-16): usuarios, amistades y tokens."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

from tests.chat_fakes import FakeChatBus, InMemoryChatRepository
from tests.fakes import InMemoryFriendsRepository, InMemoryUsersRepository

A_ID = "11111111-1111-4111-8111-111111111111"
B_ID = "22222222-2222-4222-8222-222222222222"
C_ID = "33333333-3333-4333-8333-333333333333"
D_ID = "44444444-4444-4444-8444-444444444444"  # perfil incompleto
A_SUB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B_SUB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
C_SUB = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
D_SUB = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
GHOST_SUB = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"  # token válido, sin fila en RDS
CLIENT_MESSAGE_ID = "c4a3b2a1-0000-4000-8000-111122223333"


def seed_users() -> InMemoryUsersRepository:
    users = InMemoryUsersRepository()
    users.add(A_SUB, email="ana@example.com", full_name="Ana López", dpi="1111111111111", complete=True, user_id=A_ID)
    users.add(B_SUB, email="bruno@example.com", full_name="Bruno Díaz", dpi="2222222222222", complete=True, user_id=B_ID)
    users.add(C_SUB, email="carla@example.com", full_name="Carla Ruiz", dpi="3333333333333", complete=True, user_id=C_ID)
    users.add(D_SUB, email="dina@example.com", full_name="Dina Pérez", dpi="4444444444444", complete=False, user_id=D_ID)
    return users


def make_world(build_app, *, instances: int = 1, **kwargs: Any) -> SimpleNamespace:
    """``instances`` apps sobre el MISMO bus y repositorio, como dos EC2 sobre un RDS.
    A-B son amigos; C no es amigo de nadie."""
    users = seed_users()
    friends = InMemoryFriendsRepository(users)
    friends.friendships[(A_ID, B_ID)] = None
    bus = FakeChatBus()
    repo = InMemoryChatRepository(users, friends, bus)
    apps = [
        build_app(users_repository=users, friends_repository=friends, chat_repository=repo, chat_bus=bus, **kwargs)
        for _ in range(instances)
    ]
    return SimpleNamespace(users=users, friends=friends, bus=bus, repo=repo, apps=apps)


def wait_until(condition, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condición no cumplida a tiempo")


def wait_ready(app) -> None:
    wait_until(lambda: app.state.chat_listener is not None and app.state.chat_listener.ready)


def ws_url(token: str | None, friend_id: str | None, path: str = "/ws/chat") -> str:
    parts = []
    if token is not None:
        parts.append(f"token={quote(token)}")
    if friend_id is not None:
        parts.append(f"friendId={quote(friend_id)}")
    return path + ("?" + "&".join(parts) if parts else "")


def send_frame(recipient_id: str, body: Any, client_message_id: str | None = CLIENT_MESSAGE_ID) -> dict[str, Any]:
    data: dict[str, Any] = {"recipientId": recipient_id, "body": body}
    if client_message_id is not None:
        data["clientMessageId"] = client_message_id
    return {"event": "message:send", "data": data}
