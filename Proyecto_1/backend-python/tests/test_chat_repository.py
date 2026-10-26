"""PostgresChatRepository contra una conexión falsa (PRO-16).

Sin PostgreSQL local (decisión de PRO-14): se verifica el SQL emitido, los
parámetros, que INSERT y pg_notify compartan transacción y el ROLLBACK. El SQL
real queda pendiente de ejecutar contra RDS (docs/api/python-chat.md §10).
"""

from __future__ import annotations

import json

import pytest

from app.common.errors import ApiError
from app.modules.chat.repository import (
    CHANNEL,
    MAX_NOTIFY_BYTES,
    HistoryCursor,
    NotFriends,
    PayloadTooLarge,
    PostgresChatRepository,
    StoredMessage,
    UnavailableChatRepository,
    notify_payload,
)
from tests.fakes import FakeSqlConnection, FakeSqlDatabase

ME = "11111111-1111-4111-8111-111111111111"
FRIEND = "22222222-2222-4222-8222-222222222222"
MESSAGE_ID = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
CREATED = "2026-10-26T12:00:00.123Z"
CLIENT_ID = "c4a3b2a1-0000-4000-8000-111122223333"


def repo(*results, commit_error: Exception | None = None) -> tuple[PostgresChatRepository, FakeSqlConnection]:
    conn = FakeSqlConnection(list(results), commit_error=commit_error)
    return PostgresChatRepository(FakeSqlDatabase(conn)), conn


def flat(sql: str) -> str:
    return " ".join(sql.split())


def inserted_row(body: str = "Hola") -> tuple:
    return (MESSAGE_ID, ME, FRIEND, body, CREATED)


# --- insert_message: INSERT + pg_notify en la MISMA transacción -------------------------------


def test_insert_and_notify_share_one_transaction() -> None:
    repository, conn = repo([inserted_row()], None)
    message = repository.insert_message(ME, FRIEND, "Hola", CLIENT_ID)

    assert message == StoredMessage(MESSAGE_ID, ME, FRIEND, "Hola", CREATED)
    assert len(conn.statements) == 2 and conn.committed and not conn.rolled_back
    insert_sql, insert_params = conn.statements[0]
    notify_sql, notify_params = conn.statements[1]

    sql = flat(insert_sql)
    assert sql.startswith("INSERT INTO messages (sender_id, recipient_id, content, created_at)")
    assert "WHERE EXISTS (SELECT 1 FROM friendships" in sql  # amistad dentro del propio INSERT
    assert "LEAST(%(sender)s::uuid, %(recipient)s::uuid)" in sql and "GREATEST(" in sql
    assert "date_trunc('milliseconds', clock_timestamp())" in sql
    assert "RETURNING id::text, sender_id::text, recipient_id::text, content" in sql
    assert insert_params == {"sender": ME, "recipient": FRIEND, "body": "Hola"}  # parámetros, nunca interpolado

    assert flat(notify_sql) == "SELECT pg_notify(%s, %s)"
    assert notify_params[0] == CHANNEL == "chat_messages"
    assert json.loads(notify_params[1]) == {
        "messageId": MESSAGE_ID,
        "clientMessageId": CLIENT_ID,
        "senderId": ME,
        "recipientId": FRIEND,
        "body": "Hola",
        "createdAt": CREATED,
    }


def test_notify_payload_matches_node_format_and_omits_missing_client_id() -> None:
    message = StoredMessage(MESSAGE_ID, ME, FRIEND, "Hola, ¿cómo estás? 😀", CREATED)
    payload = notify_payload(message, None)
    assert payload == (
        '{"messageId":"%s","senderId":"%s","recipientId":"%s","body":"Hola, ¿cómo estás? 😀","createdAt":"%s"}'
        % (MESSAGE_ID, ME, FRIEND, CREATED)
    )  # claves en el orden de Node, UTF-8 sin escapar, sin clientMessageId


def test_not_friends_inserts_nothing_and_does_not_notify() -> None:
    repository, conn = repo(None)
    with pytest.raises(NotFriends):
        repository.insert_message(ME, FRIEND, "Hola", None)
    assert len(conn.statements) == 1 and not conn.committed


def test_payload_over_limit_rolls_back_the_insert() -> None:
    repository, conn = repo([inserted_row("😀" * 4000)], None)
    with pytest.raises(PayloadTooLarge):
        repository.insert_message(ME, FRIEND, "😀" * 4000, None)
    assert conn.rolled_back and not conn.committed
    assert all("pg_notify" not in sql for sql, _ in conn.statements)
    assert MAX_NOTIFY_BYTES < 8000


def test_commit_failure_propagates() -> None:
    repository, conn = repo([inserted_row()], None, commit_error=ConnectionError("commit"))
    with pytest.raises(ConnectionError):
        repository.insert_message(ME, FRIEND, "Hola", None)
    assert not conn.committed


def test_database_error_during_insert_propagates() -> None:
    repository, _ = repo(ConnectionError("rds caído"))
    with pytest.raises(ConnectionError):
        repository.insert_message(ME, FRIEND, "Hola", None)


# --- amistad y existencia ----------------------------------------------------------------------------


def test_are_friends_uses_canonical_pair_and_short_circuits_self() -> None:
    repository, conn = repo([(1,)], None)
    assert repository.are_friends(ME, FRIEND) is True
    sql, params = conn.statements[0]
    assert "user_low_id = LEAST(%(a)s::uuid, %(b)s::uuid)" in flat(sql)
    assert "user_high_id = GREATEST(%(a)s::uuid, %(b)s::uuid)" in flat(sql)
    assert params == {"a": ME, "b": FRIEND}
    assert repository.are_friends(ME, FRIEND) is False  # sin fila
    assert repository.are_friends(ME, ME) is False
    assert len(conn.statements) == 2  # ME-ME no consulta


def test_friend_exists() -> None:
    repository, conn = repo([(1,)], None)
    assert repository.friend_exists(FRIEND) is True
    assert repository.friend_exists(FRIEND) is False
    assert flat(conn.statements[0][0]) == "SELECT 1 FROM users WHERE id = %s::uuid"


# --- historial ----------------------------------------------------------------------------------------------


def test_list_messages_conversation_query_and_params() -> None:
    row = (MESSAGE_ID, ME, FRIEND, "Hola", CREATED, None)
    repository, conn = repo([row])
    rows = repository.list_messages(ME, FRIEND, None, 51)

    assert rows == [StoredMessage(MESSAGE_ID, ME, FRIEND, "Hola", CREATED, None)]
    sql, params = conn.statements[0]
    sql = flat(sql)
    assert "FROM messages m" in sql
    assert "LEAST(m.sender_id, m.recipient_id) = LEAST(%(me)s::uuid, %(friend)s::uuid)" in sql  # índice 002
    assert "GREATEST(m.sender_id, m.recipient_id) = GREATEST(%(me)s::uuid, %(friend)s::uuid)" in sql
    assert "ORDER BY m.created_at DESC, m.id DESC LIMIT %(limit)s" in sql
    assert params == {"me": ME, "friend": FRIEND, "ts": None, "cid": None, "limit": 51}


def test_list_messages_with_node_cursor_compares_only_created_at() -> None:
    repository, conn = repo([])
    repository.list_messages(ME, FRIEND, HistoryCursor(CREATED), 10)
    sql, params = conn.statements[0]
    assert "m.created_at < %(ts)s::timestamptz" in flat(sql)
    assert params["ts"] == CREATED and params["cid"] is None


def test_list_messages_with_common_cursor_uses_created_at_and_id() -> None:
    repository, conn = repo([])
    repository.list_messages(ME, FRIEND, HistoryCursor("2026-10-26T12:00:00.123456Z", MESSAGE_ID), 10)
    sql, params = conn.statements[0]
    assert "(m.created_at, m.id) < (%(ts)s::timestamptz, %(cid)s::uuid)" in flat(sql)
    assert params["cid"] == MESSAGE_ID


def test_unavailable_repository_is_503_everywhere() -> None:
    unavailable = UnavailableChatRepository()
    for call in (
        lambda: unavailable.friend_exists(FRIEND),
        lambda: unavailable.are_friends(ME, FRIEND),
        lambda: unavailable.insert_message(ME, FRIEND, "x", None),
        lambda: unavailable.list_messages(ME, FRIEND, None, 1),
    ):
        with pytest.raises(ApiError) as error:
            call()
        assert error.value.status_code == 503
