"""Dobles del chat (PRO-16): bus LISTEN/NOTIFY falso y repositorio en memoria."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta

from psycopg import OperationalError

from app.modules.chat.repository import (
    MAX_NOTIFY_BYTES,
    HistoryCursor,
    NotFriends,
    PayloadTooLarge,
    StoredMessage,
    notify_payload,
)
from tests.fakes import CLOCK_START, InMemoryFriendsRepository, InMemoryUsersRepository


class FakeListenConnection:
    """Sesión LISTEN falsa: recibe lo que se publica en el bus mientras esté suscrita."""

    def __init__(self) -> None:
        self.inbox: queue.Queue[str] = queue.Queue()
        self.listening = False
        self.broken = False
        self.closed = False

    def listen(self, channel: str) -> None:
        assert channel == "chat_messages"
        self.listening = True

    def notifies(self, timeout: float) -> Iterator[str]:
        deadline = time.monotonic() + timeout
        while True:
            if self.broken:
                raise OperationalError("conexión perdida")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            try:
                yield self.inbox.get(timeout=min(remaining, 0.02))
            except queue.Empty:
                continue

    def close(self) -> None:
        self.closed = True
        self.listening = False


class FakeChatBus:
    """Imita LISTEN/NOTIFY de un RDS compartido por varias instancias (apps)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.connections: list[FakeListenConnection] = []
        self.connect_attempts = 0
        self.fail_connects = 0  # intentos de conexión que fallan antes de funcionar
        self.published: list[str] = []

    def connect(self) -> FakeListenConnection:
        with self._lock:
            self.connect_attempts += 1
            if self.fail_connects > 0:
                self.fail_connects -= 1
                raise OperationalError("RDS no responde")
            conn = FakeListenConnection()
            self.connections.append(conn)
            return conn

    def publish(self, payload: str) -> None:
        """pg_notify: solo llega a las sesiones con LISTEN activo (tras el COMMIT)."""
        with self._lock:
            self.published.append(payload)
            for conn in self.connections:
                if conn.listening:
                    conn.inbox.put(payload)

    def drop_connections(self) -> None:
        with self._lock:
            for conn in self.connections:
                conn.broken = True


class InMemoryChatRepository:
    """Implementa el Protocol de ``app/modules/chat/repository.py`` con las mismas
    reglas que PostgreSQL: amistad dentro del INSERT y NOTIFY solo tras el commit
    (descartado junto con el INSERT si el payload excede el límite). Solo pruebas."""

    def __init__(self, users: InMemoryUsersRepository, friends: InMemoryFriendsRepository, bus: FakeChatBus) -> None:
        self.users = users
        self.friends = friends
        self.bus = bus
        self.rows: list[StoredMessage] = []
        self.fail_with: Exception | None = None
        self._lock = threading.Lock()
        self._ticks = 0

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def friend_exists(self, user_id: str) -> bool:
        self._check()
        return any(row.id == user_id for row in self.users.rows.values())

    def are_friends(self, user_a: str, user_b: str) -> bool:
        self._check()
        if user_a == user_b:
            return False
        pair = (user_a, user_b) if user_a < user_b else (user_b, user_a)
        return pair in self.friends.friendships

    def insert_message(
        self, sender_id: str, recipient_id: str, body: str, client_message_id: str | None
    ) -> StoredMessage:
        self._check()
        if not self.are_friends(sender_id, recipient_id):
            raise NotFriends()
        with self._lock:
            self._ticks += 1
            moment = CLOCK_START + timedelta(milliseconds=self._ticks)
        created = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
        message = StoredMessage(str(uuid.uuid4()), sender_id, recipient_id, body, created)
        payload = notify_payload(message, client_message_id)
        if len(payload.encode("utf-8")) > MAX_NOTIFY_BYTES:
            raise PayloadTooLarge()
        with self._lock:
            self.rows.append(message)
        self.bus.publish(payload)
        return message

    def list_messages(
        self, user_id: str, friend_id: str, after: HistoryCursor | None, limit: int
    ) -> list[StoredMessage]:
        self._check()
        pair = {user_id, friend_id}
        rows = [m for m in self.rows if {m.sender_id, m.recipient_id} == pair]
        if after is not None:
            if after.message_id is None:
                rows = [m for m in rows if m.created_at < after.created_at]
            else:
                rows = [m for m in rows if (m.created_at, m.id) < (after.created_at, after.message_id)]
        rows.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        return rows[:limit]
