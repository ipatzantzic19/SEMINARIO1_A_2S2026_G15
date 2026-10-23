"""PostgresFriendsRepository contra una conexión falsa, y el cursor común.

Sin PostgreSQL local (decisión de PRO-14): estas pruebas verifican el SQL
emitido (tablas, casts, filtros, orden), los parámetros, las transacciones, el
ROLLBACK y la traducción de errores de psycopg. El SQL real queda pendiente de
ejecutar contra RDS (docs/api/python-friends.md §9).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from types import SimpleNamespace

import psycopg
import pytest

from app.modules.social.cursor import CursorPosition, InvalidCursor, decode_cursor, encode_cursor
from app.modules.social.repository import (
    AddresseeNotFound,
    AlreadyAnswered,
    AlreadyFriends,
    NotAddressee,
    PostgresFriendsRepository,
    RequestNotFound,
    RequestPending,
    UnavailableFriendsRepository,
)
from app.common.errors import ApiError
from tests.fakes import FakeSqlConnection, FakeSqlDatabase

ME = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
THIRD = "33333333-3333-4333-8333-333333333333"
REQUEST_ID = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
WHEN = datetime(2026, 10, 18, 18, 45, 0, 123456, tzinfo=timezone.utc)
KEY = "Fotos_Perfil/public/x/00000000-0000-4000-8000-000000000001.webp"


def repo(*results, commit_error: Exception | None = None) -> tuple[PostgresFriendsRepository, FakeSqlConnection]:
    conn = FakeSqlConnection(list(results), commit_error=commit_error)
    return PostgresFriendsRepository(FakeSqlDatabase(conn)), conn


def violation(cls: type[psycopg.Error], constraint: str) -> psycopg.Error:
    class _Violation(cls):  # type: ignore[valid-type, misc]
        diag = SimpleNamespace(constraint_name=constraint)  # type: ignore[assignment]

    return _Violation("violación")


def request_row(status: str = "pending", requester: str = ME, addressee: str = OTHER) -> tuple:
    return (REQUEST_ID, status, WHEN, requester, "Ana López", KEY, addressee, "Bruno Díaz", KEY)


def flatten(sql: str) -> str:
    return " ".join(sql.split())


# --- Cursor ---------------------------------------------------------------------

CURSOR_TS = "2026-10-20T12:00:00.123456Z"


def test_cursor_round_trip_is_base64url_without_padding() -> None:
    cursor = encode_cursor(CURSOR_TS, OTHER)
    assert "=" not in cursor and "+" not in cursor and "/" not in cursor
    assert base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode() == f"{CURSOR_TS}#{OTHER}"
    assert decode_cursor(cursor) == CursorPosition(CURSOR_TS, OTHER)


def test_cursor_accepts_standard_base64_with_or_without_padding() -> None:
    raw = f"{CURSOR_TS}#{OTHER}".encode()
    for variant in (base64.b64encode(raw).decode(), base64.b64encode(raw).decode().rstrip("=")):
        assert decode_cursor(variant) == CursorPosition(CURSOR_TS, OTHER)


def test_cursor_normalizes_uuid_case() -> None:
    assert decode_cursor(encode_cursor(CURSOR_TS, OTHER.upper())).user_id == OTHER


@pytest.mark.parametrize(
    "text",
    [
        f"2026-10-20T12:00:00Z#{OTHER}",  # sin 6 decimales
        f"2026-10-20T12:00:00.123Z#{OTHER}",  # solo milisegundos (formato de Node)
        f"2026-10-20 12:00:00.123456Z#{OTHER}",
        f"2026-13-20T12:00:00.123456Z#{OTHER}",
        f"2026-10-20T12:00:00.123456Z#{OTHER}#extra",
        f"2026-10-20T12:00:00.123456Z#",
        "#",
        "",
    ],
)
def test_cursor_rejects_other_formats(text: str) -> None:
    with pytest.raises(InvalidCursor):
        decode_cursor(base64.urlsafe_b64encode(text.encode()).decode())


def test_cursor_rejects_garbage() -> None:
    for value in ("", "***", "====", "é", "A" * 201):
        with pytest.raises(InvalidCursor):
            decode_cursor(value)


# --- Lecturas ---------------------------------------------------------------------


def test_list_non_friends_sql_and_params() -> None:
    repository, conn = repo([(OTHER, "Bruno Díaz", KEY, CURSOR_TS)])
    rows = repository.list_non_friends(ME, CursorPosition(CURSOR_TS, THIRD), 21)
    assert [(r.user.id, r.cursor_at) for r in rows] == [(OTHER, CURSOR_TS)]
    sql, params = conn.statements[0]
    text = flatten(sql)
    assert "FROM users u" in text and "u.id <> %(me)s::uuid" in text
    assert "u.profile_image_key IS NOT NULL" in text  # sin perfiles incompletos
    assert "NOT EXISTS (SELECT 1 FROM friendships f" in text  # excluye amigos...
    assert "friend_requests" not in text  # ...pero no a quienes tienen solicitud pendiente
    assert "LEAST(u.id, %(me)s::uuid)" in text and "GREATEST(u.id, %(me)s::uuid)" in text
    assert "(u.created_at, u.id) < (%(ts)s::timestamptz, %(cid)s::uuid)" in text
    assert "ORDER BY u.created_at DESC, u.id DESC" in text and "LIMIT %(limit)s" in text
    assert "SS.US" in text  # microsegundos exactos con to_char
    assert params == {"me": ME, "ts": CURSOR_TS, "cid": THIRD, "limit": 21}


def test_list_non_friends_first_page_has_no_cursor_params() -> None:
    repository, conn = repo([])
    assert repository.list_non_friends(ME, None, 21) == []
    assert conn.statements[0][1] == {"me": ME, "ts": None, "cid": None, "limit": 21}


def test_list_requests_only_pending_both_directions() -> None:
    repository, conn = repo([request_row()])
    [record] = repository.list_requests(ME)
    assert (record.id, record.status, record.created_at) == (REQUEST_ID, "pending", WHEN)
    assert (record.requester.full_name, record.addressee.id) == ("Ana López", OTHER)
    text = flatten(conn.statements[0][0])
    assert "fr.status = 'pending'" in text
    assert "fr.requester_id = %(me)s::uuid OR fr.addressee_id = %(me)s::uuid" in text
    assert "ORDER BY fr.created_at DESC, fr.id DESC" in text
    assert conn.statements[0][1] == {"me": ME}


def test_list_friends_uses_both_index_directions_and_orders_by_name_and_id() -> None:
    repository, conn = repo([(OTHER, "Bruno Díaz", KEY)])
    [friend] = repository.list_friends(ME)
    assert (friend.id, friend.full_name) == (OTHER, "Bruno Díaz")
    text = flatten(conn.statements[0][0])
    assert "FROM friendships WHERE user_low_id = %(me)s::uuid" in text
    assert "FROM friendships WHERE user_high_id = %(me)s::uuid" in text
    assert "UNION ALL" in text and "ORDER BY u.full_name ASC, u.id ASC" in text


# --- POST: crear solicitud ------------------------------------------------------------


def test_create_request_checks_then_inserts_in_one_transaction() -> None:
    repository, conn = repo(
        [(ME, "Ana López", KEY), (OTHER, "Bruno Díaz", KEY)],  # usuarios
        None,  # sin amistad
        [(REQUEST_ID, "pending", WHEN)],  # INSERT ... RETURNING
    )
    record = repository.create_request(ME, OTHER)
    assert (record.id, record.status, record.created_at) == (REQUEST_ID, "pending", WHEN)
    assert (record.requester.id, record.addressee.id) == (ME, OTHER)
    statements = [flatten(sql) for sql, _ in conn.statements]
    assert "FROM users WHERE id IN (%s::uuid, %s::uuid)" in statements[0]
    assert "LEAST(%(a)s::uuid, %(b)s::uuid)" in statements[1] and "FROM friendships" in statements[1]
    assert statements[2].startswith("INSERT INTO friend_requests (requester_id, addressee_id)")
    assert conn.statements[2][1] == (ME, OTHER)
    assert conn.committed and not conn.rolled_back
    assert not any("advisory" in s for s in statements)  # decisión: sin bloqueo consultivo


@pytest.mark.parametrize(
    "users",
    [
        [(ME, "Ana López", KEY)],  # destinatario inexistente
        [(ME, "Ana López", KEY), (OTHER, "Dina Pérez", None)],  # perfil incompleto
    ],
    ids=["inexistente", "perfil-incompleto"],
)
def test_create_request_hides_missing_and_incomplete_addressee(users: list) -> None:
    repository, conn = repo(users)
    with pytest.raises(AddresseeNotFound):
        repository.create_request(ME, OTHER)
    assert conn.rolled_back and len(conn.statements) == 1  # no inserta nada


def test_create_request_already_friends_does_not_insert() -> None:
    repository, conn = repo([(ME, "A", KEY), (OTHER, "B", KEY)], [(1,)])
    with pytest.raises(AlreadyFriends):
        repository.create_request(ME, OTHER)
    assert conn.rolled_back and len(conn.statements) == 2


def test_create_request_pending_pair_violation_is_request_pending() -> None:
    error = violation(psycopg.errors.UniqueViolation, "friend_requests_one_pending_pair_idx")
    repository, conn = repo([(ME, "A", KEY), (OTHER, "B", KEY)], None, error)
    with pytest.raises(RequestPending):
        repository.create_request(ME, OTHER)
    assert conn.rolled_back and not conn.committed


def test_create_request_unknown_unique_violation_is_not_swallowed() -> None:
    error = violation(psycopg.errors.UniqueViolation, "otro_indice")
    repository, _ = repo([(ME, "A", KEY), (OTHER, "B", KEY)], None, error)
    with pytest.raises(psycopg.errors.UniqueViolation):
        repository.create_request(ME, OTHER)


def test_create_request_foreign_key_violation_is_addressee_not_found() -> None:
    error = violation(psycopg.errors.ForeignKeyViolation, "friend_requests_addressee_id_fkey")
    repository, _ = repo([(ME, "A", KEY), (OTHER, "B", KEY)], None, error)
    with pytest.raises(AddresseeNotFound):
        repository.create_request(ME, OTHER)


# --- PATCH: responder -------------------------------------------------------------------


def test_accept_locks_row_updates_with_pending_guard_and_inserts_ordered_friendship() -> None:
    repository, conn = repo([request_row()], [("accepted",)], None)
    record = repository.answer_request(REQUEST_ID, OTHER, "accepted")
    assert record.status == "accepted" and record.created_at == WHEN
    texts = [flatten(sql) for sql, _ in conn.statements]
    assert "WHERE fr.id = %s::uuid FOR UPDATE OF fr" in texts[0]
    assert "SET status = %(status)s::friend_request_status, responded_at = now()" in texts[1]
    assert "WHERE id = %(id)s::uuid AND status = 'pending'" in texts[1]
    assert "INSERT INTO friendships (user_low_id, user_high_id, request_id)" in texts[2]
    assert "LEAST(%(a)s::uuid, %(b)s::uuid), GREATEST(%(a)s::uuid, %(b)s::uuid)" in texts[2]
    assert "ON CONFLICT" not in texts[2]  # un duplicado debe fallar, no ocultarse
    assert conn.statements[1][1] == {"status": "accepted", "id": REQUEST_ID}
    assert conn.statements[2][1] == {"a": ME, "b": OTHER, "request": REQUEST_ID}
    assert conn.committed and not conn.rolled_back


def test_reject_does_not_create_friendship() -> None:
    repository, conn = repo([request_row()], [("rejected",)])
    assert repository.answer_request(REQUEST_ID, OTHER, "rejected").status == "rejected"
    assert len(conn.statements) == 2 and conn.committed
    assert not any("friendships" in sql for sql, _ in conn.statements)


def test_answer_unknown_request() -> None:
    repository, conn = repo(None)
    with pytest.raises(RequestNotFound):
        repository.answer_request(REQUEST_ID, OTHER, "accepted")
    assert conn.rolled_back


@pytest.mark.parametrize("responder", [ME, THIRD], ids=["solicitante", "tercero"])
def test_only_addressee_may_answer(responder: str) -> None:
    repository, conn = repo([request_row()])
    with pytest.raises(NotAddressee):
        repository.answer_request(REQUEST_ID, responder, "accepted")
    assert len(conn.statements) == 1 and conn.rolled_back  # no hay UPDATE ni INSERT


@pytest.mark.parametrize("status", ["accepted", "rejected", "canceled"])
def test_not_pending_is_already_answered(status: str) -> None:
    repository, conn = repo([request_row(status=status)])
    with pytest.raises(AlreadyAnswered):
        repository.answer_request(REQUEST_ID, OTHER, "accepted")
    assert len(conn.statements) == 1 and conn.rolled_back


def test_update_that_matches_no_row_is_already_answered() -> None:
    repository, conn = repo([request_row()], None)  # otro proceso respondió entre medio
    with pytest.raises(AlreadyAnswered):
        repository.answer_request(REQUEST_ID, OTHER, "accepted")
    assert conn.rolled_back and len(conn.statements) == 2


@pytest.mark.parametrize("constraint", ["friendships_pkey", "friendships_request_id_key"])
def test_existing_friendship_rolls_back_the_whole_answer(constraint: str) -> None:
    error = violation(psycopg.errors.UniqueViolation, constraint)
    repository, conn = repo([request_row()], [("accepted",)], error)
    with pytest.raises(AlreadyFriends):
        repository.answer_request(REQUEST_ID, OTHER, "accepted")
    assert conn.rolled_back and not conn.committed  # la solicitud sigue pendiente


def test_failed_commit_is_not_reported_as_success() -> None:
    repository, conn = repo([request_row()], [("accepted",)], None, commit_error=psycopg.OperationalError("commit"))
    with pytest.raises(psycopg.OperationalError):
        repository.answer_request(REQUEST_ID, OTHER, "accepted")
    assert not conn.committed


def test_unavailable_repository_always_503() -> None:
    unavailable = UnavailableFriendsRepository()
    calls = (
        lambda: unavailable.list_non_friends(ME, None, 21),
        lambda: unavailable.list_requests(ME),
        lambda: unavailable.list_friends(ME),
        lambda: unavailable.create_request(ME, OTHER),
        lambda: unavailable.answer_request(REQUEST_ID, ME, "accepted"),
    )
    for call in calls:
        with pytest.raises(ApiError) as error:
            call()
        assert error.value.status_code == 503
