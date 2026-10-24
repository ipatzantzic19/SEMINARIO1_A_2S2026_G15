"""PostgresPostsRepository contra una conexión falsa.

Sin PostgreSQL local (decisión de PRO-14): estas pruebas verifican el SQL emitido
(tablas, casts, visibilidad, orden, ON CONFLICT), los parámetros, las transacciones
y el ROLLBACK. El SQL real queda pendiente de ejecutar contra RDS
(docs/api/python-posts.md §11).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.integrations.rekognition.labels import NormalizedLabel
from app.modules.posts.repository import (
    CommentRecord,
    LabelCount,
    PostgresPostsRepository,
    NotFriendOrAuthor,
    PostNotFound,
    escape_like,
)
from app.modules.social.cursor import CursorPosition
from tests.fakes import FakeSqlConnection, FakeSqlDatabase

ME = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
POST_ID = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
WHEN = datetime(2026, 10, 18, 18, 45, 0, 123456, tzinfo=timezone.utc)
KEY = "Fotos_Publicadas/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/00000000-0000-4000-8000-000000000001.jpg"
AVATAR = "Fotos_Perfil/public/x/00000000-0000-4000-8000-000000000001.webp"


def repo(*results, commit_error: Exception | None = None) -> tuple[PostgresPostsRepository, FakeSqlConnection]:
    conn = FakeSqlConnection(list(results), commit_error=commit_error)
    return PostgresPostsRepository(FakeSqlDatabase(conn)), conn


def flatten(sql: str) -> str:
    return " ".join(sql.split())


def feed_row(post_id: str = POST_ID) -> tuple:
    return (post_id, "Mi perro", KEY, WHEN, "2026-10-18T18:45:00.123456Z", OTHER, "Bruno Díaz", AVATAR, ["perro", "exterior"], 3)


def labels(*items: tuple[str, str, str]) -> list[NormalizedLabel]:
    return [NormalizedLabel(name, Decimal(confidence), source) for name, confidence, source in items]


# --- GET /posts -----------------------------------------------------------------------


def test_feed_sql_visibility_filter_cursor_order_and_limit() -> None:
    repository, conn = repo([])
    assert repository.list_feed(ME, "perro", CursorPosition("2026-10-20T12:00:00.123456Z", OTHER), 21) == []
    sql, params = conn.statements[0]
    text = flatten(sql)
    assert "FROM posts p JOIN users u ON u.id = p.author_id" in text
    # Autor propio o amigo con la tabla canónica de amistades.
    assert "p.author_id = %(me)s::uuid" in text
    assert "f.user_low_id = LEAST(p.author_id, %(me)s::uuid)" in text
    assert "f.user_high_id = GREATEST(p.author_id, %(me)s::uuid)" in text
    # Filtro por etiqueta: igualdad sobre normalized_label (citext).
    assert "pl.normalized_label = %(label)s::citext" in text
    # Cursor por tupla (created_at, id) y orden total.
    assert "(p.created_at, p.id) < (%(ts)s::timestamptz, %(cid)s::uuid)" in text
    assert text.endswith("ORDER BY p.created_at DESC, p.id DESC LIMIT %(limit)s")
    assert "to_char(p.created_at AT TIME ZONE 'UTC'" in text and "SS.US" in text  # 6 decimales
    assert "c.deleted_at IS NULL" in text  # commentsCount ignora comentarios borrados
    assert params == {"me": ME, "label": "perro", "ts": "2026-10-20T12:00:00.123456Z", "cid": OTHER, "limit": 21}


def test_feed_first_page_without_label_sends_nulls() -> None:
    repository, conn = repo([])
    repository.list_feed(ME, None, None, 21)
    assert conn.statements[0][1] == {"me": ME, "label": None, "ts": None, "cid": None, "limit": 21}


def test_feed_maps_rows() -> None:
    repository, _ = repo([feed_row()])
    (row,) = repository.list_feed(ME, None, None, 21)
    assert row.cursor_at == "2026-10-18T18:45:00.123456Z"
    post = row.post
    assert (post.id, post.description, post.image_key, post.created_at) == (POST_ID, "Mi perro", KEY, WHEN)
    assert (post.author.id, post.author.full_name, post.author.profile_image_key) == (OTHER, "Bruno Díaz", AVATAR)
    assert post.labels == ("perro", "exterior") and post.comments_count == 3


def test_user_text_is_never_interpolated_into_sql() -> None:
    hostile = "x'; DROP TABLE posts; --"
    repository, conn = repo([], [])
    repository.list_feed(ME, hostile, None, 21)
    repository.list_labels(ME, hostile)
    for sql, _ in conn.statements:
        assert "DROP TABLE" not in sql and hostile not in sql


# --- POST /posts ------------------------------------------------------------------------


def test_create_post_inserts_post_and_labels_in_one_transaction() -> None:
    repository, conn = repo([(POST_ID, WHEN)], None)
    post_id, created_at = repository.create_post(
        ME, KEY, "Mi perro", labels(("perro", "98.12", "Dog"), ("exterior", "91.44", "Outdoors"))
    )
    assert (post_id, created_at) == (POST_ID, WHEN)
    assert conn.committed and not conn.rolled_back
    (post_sql, post_params), (label_sql, label_params) = conn.statements
    assert flatten(post_sql).startswith("INSERT INTO posts (author_id, description, image_key) VALUES")
    assert post_params == (ME, "Mi perro", KEY)
    text = flatten(label_sql)
    assert "INSERT INTO post_labels (post_id, normalized_label, confidence, source_label)" in text
    assert "unnest(%(names)s::text[], %(confidences)s::numeric[], %(sources)s::text[])" in text
    assert "ON CONFLICT (post_id, normalized_label) DO UPDATE SET" in text
    assert "confidence = EXCLUDED.confidence, source_label = EXCLUDED.source_label" in text
    assert label_params == {
        "post": POST_ID,
        "names": ["perro", "exterior"],
        "confidences": [Decimal("98.12"), Decimal("91.44")],
        "sources": ["Dog", "Outdoors"],
    }


def test_create_post_without_labels_skips_label_insert() -> None:
    repository, conn = repo([(POST_ID, WHEN)])
    repository.create_post(ME, KEY, None, [])
    assert len(conn.statements) == 1 and conn.statements[0][1] == (ME, None, KEY)
    assert conn.committed


def test_create_post_rolls_back_when_labels_fail() -> None:
    repository, conn = repo([(POST_ID, WHEN)], RuntimeError("falla al insertar etiquetas"))
    with pytest.raises(RuntimeError):
        repository.create_post(ME, KEY, None, labels(("perro", "98.12", "Dog")))
    assert conn.rolled_back and not conn.committed


def test_create_post_commit_failure_propagates_without_commit() -> None:
    repository, conn = repo([(POST_ID, WHEN)], None, commit_error=ConnectionError("commit"))
    with pytest.raises(ConnectionError):
        repository.create_post(ME, KEY, None, labels(("perro", "98.12", "Dog")))
    assert not conn.committed


def test_create_post_without_returning_row_is_an_error() -> None:
    repository, conn = repo(None)
    with pytest.raises(RuntimeError):
        repository.create_post(ME, KEY, None, [])
    assert conn.rolled_back


# --- GET /labels -------------------------------------------------------------------------


def test_labels_sql_groups_visible_posts_and_filters_with_escaped_pattern() -> None:
    repository, conn = repo([("perro", 2), ("gato", 1)])
    assert repository.list_labels(ME, "100%_a\\b") == [LabelCount("perro", 2), LabelCount("gato", 1)]
    sql, params = conn.statements[0]
    text = flatten(sql)
    assert "FROM posts p JOIN post_labels pl ON pl.post_id = p.id" in text
    assert "p.author_id = %(me)s::uuid" in text and "f.user_low_id = LEAST(p.author_id, %(me)s::uuid)" in text
    assert "pl.normalized_label::text ILIKE %(pattern)s::text" in text
    assert text.endswith("GROUP BY pl.normalized_label ORDER BY post_count DESC, name ASC")
    assert params == {"me": ME, "pattern": "%100\\%\\_a\\\\b%"}


def test_labels_without_query_sends_null_pattern() -> None:
    repository, conn = repo([])
    repository.list_labels(ME, None)
    assert conn.statements[0][1] == {"me": ME, "pattern": None}


@pytest.mark.parametrize(
    ("raw", "escaped"), [("perro", "perro"), ("100%", "100\\%"), ("a_b", "a\\_b"), ("a\\b", "a\\\\b"), ("%_\\", "\\%\\_\\\\")]
)
def test_escape_like(raw: str, escaped: str) -> None:
    assert escape_like(raw) == escaped


# --- Comentarios ---------------------------------------------------------------------------


def comment_row(comment_id: str = POST_ID, body: str = "¡Qué buena foto!") -> tuple:
    return (comment_id, body, WHEN, OTHER, "Bruno Díaz", AVATAR)


def test_list_comments_checks_visibility_then_orders_chronologically() -> None:
    repository, conn = repo([(True,)], [comment_row(), comment_row(OTHER, "segundo")])
    comments = repository.list_comments(ME, POST_ID)
    assert [c.body for c in comments] == ["¡Qué buena foto!", "segundo"]
    assert isinstance(comments[0], CommentRecord) and comments[0].author.full_name == "Bruno Díaz"
    (visible_sql, visible_params), (list_sql, list_params) = conn.statements
    assert "p.id = %(post)s::uuid" in flatten(visible_sql) and "friendships" in flatten(visible_sql)
    assert visible_params == {"me": ME, "post": POST_ID}
    text = flatten(list_sql)
    assert "c.deleted_at IS NULL" in text and text.endswith("ORDER BY c.created_at ASC, c.id ASC")
    assert list_params == {"post": POST_ID}


def test_list_comments_of_missing_post_raises_not_found_without_reading_comments() -> None:
    repository, conn = repo(None)  # sin fila: la publicación no existe
    with pytest.raises(PostNotFound):
        repository.list_comments(ME, POST_ID)
    assert len(conn.statements) == 1


def test_list_comments_of_foreign_post_raises_forbidden_without_reading_comments() -> None:
    repository, conn = repo([(False,)])  # existe, pero no es autor ni amigo
    with pytest.raises(NotFriendOrAuthor):
        repository.list_comments(ME, POST_ID)
    assert len(conn.statements) == 1


def test_create_comment_is_a_single_visibility_checked_insert() -> None:
    repository, conn = repo([comment_row()])
    comment = repository.create_comment(ME, POST_ID, "¡Qué buena foto!")
    assert comment.body == "¡Qué buena foto!" and comment.author.id == OTHER and comment.created_at == WHEN
    assert conn.committed and len(conn.statements) == 1
    sql, params = conn.statements[0]
    text = flatten(sql)
    assert text.startswith("WITH target AS (SELECT p.id FROM posts p WHERE p.id = %(post)s::uuid AND (")
    assert "friendships" in text  # la comprobación de amistad va en la misma sentencia
    assert "INSERT INTO comments (post_id, author_id, content) SELECT t.id, %(me)s::uuid, %(body)s FROM target t" in text
    assert params == {"me": ME, "post": POST_ID, "body": "¡Qué buena foto!"}


def test_create_comment_on_missing_post_raises_not_found_and_writes_nothing() -> None:
    repository, conn = repo(None, None)  # el INSERT no devuelve fila y la publicación no existe
    with pytest.raises(PostNotFound):
        repository.create_comment(ME, POST_ID, "hola")
    assert "INSERT INTO comments" in conn.statements[0][0]
    assert flatten(conn.statements[1][0]) == "SELECT 1 FROM posts WHERE id = %(post)s::uuid"
    assert conn.statements[1][1] == {"post": POST_ID}


def test_create_comment_on_foreign_post_raises_forbidden_and_writes_nothing() -> None:
    repository, conn = repo(None, [(1,)])  # el INSERT no devuelve fila, pero la publicación existe
    with pytest.raises(NotFriendOrAuthor):
        repository.create_comment(ME, POST_ID, "hola")
    assert len(conn.statements) == 2 and conn.committed  # la transacción del INSERT no escribió nada


def test_create_comment_database_error_rolls_back() -> None:
    repository, conn = repo(RuntimeError("rds caída"))
    with pytest.raises(RuntimeError):
        repository.create_comment(ME, POST_ID, "hola")
    assert conn.rolled_back and not conn.committed
