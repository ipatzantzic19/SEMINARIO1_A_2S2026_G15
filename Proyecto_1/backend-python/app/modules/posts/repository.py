"""Acceso a ``posts``, ``post_labels`` y ``comments`` (PRO-34).

El SQL completo y su justificación están en docs/api/python-posts.md §5.

- Sin respaldo en memoria: si RDS falla, la excepción llega al servicio, que
  responde 503. El único repositorio en memoria vive en las pruebas.
- Visibilidad: una publicación es visible para su autor y para sus amigos
  (``friendships`` con orden canónico ``user_low_id < user_high_id``). En los
  comentarios se distingue una publicación inexistente (``PostNotFound``, 404) de
  una que existe pero no es visible (``NotFriendOrAuthor``, 403).
- ``POST /posts``: ``posts`` y ``post_labels`` se escriben en una sola
  transacción; las etiquetas ya vienen calculadas (Rekognition se invoca antes y
  fuera de la transacción, para no retener una conexión durante la llamada AWS).
- ``POST /comments``: un único ``INSERT ... SELECT`` comprueba la visibilidad y
  escribe; no hay ventana entre la comprobación y la escritura. No se usa
  ``FOR UPDATE``: no existe ninguna ruta que borre publicaciones ni amistades.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.common.errors import ServiceUnavailableError
from app.modules.integrations.rekognition.labels import NormalizedLabel
from app.modules.social.cursor import CursorPosition
from app.modules.social.repository import PublicUserRecord


@dataclass(frozen=True)
class PostRecord:
    id: str
    author: PublicUserRecord
    description: str | None
    image_key: str
    labels: tuple[str, ...]
    comments_count: int
    created_at: datetime


@dataclass(frozen=True)
class FeedRow:
    """Fila del feed; ``cursor_at`` es el texto de ``to_char`` (6 decimales)."""

    post: PostRecord
    cursor_at: str


@dataclass(frozen=True)
class CommentRecord:
    id: str
    author: PublicUserRecord
    body: str
    created_at: datetime


@dataclass(frozen=True)
class LabelCount:
    name: str
    post_count: int


class PostNotFound(Exception):
    """La publicación no existe (404)."""


class NotFriendOrAuthor(Exception):
    """La publicación existe pero el usuario no es su autor ni su amigo (403 NOT_FRIEND_OR_AUTHOR)."""


class PostsRepository(Protocol):
    def list_feed(self, me_id: str, label: str | None, after: CursorPosition | None, limit: int) -> list[FeedRow]:
        """Hasta ``limit`` filas (el servicio pide ``limite + 1`` para saber si hay más)."""

    def create_post(
        self, author_id: str, image_key: str, description: str | None, labels: Sequence[NormalizedLabel]
    ) -> tuple[str, datetime]:
        """Inserta la publicación y sus etiquetas en una transacción; devuelve ``(id, created_at)``."""

    def list_labels(self, me_id: str, query: str | None) -> list[LabelCount]: ...

    def list_comments(self, me_id: str, post_id: str) -> list[CommentRecord]:
        """Raises: PostNotFound, NotFriendOrAuthor."""

    def create_comment(self, me_id: str, post_id: str, body: str) -> CommentRecord:
        """Raises: PostNotFound, NotFriendOrAuthor."""


_CURSOR_TEXT = "to_char(p.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')"

# Autor propio o amigo. Parámetro %(me)s::uuid; usa el alias ``p`` de posts.
_VISIBLE = (
    "(p.author_id = %(me)s::uuid OR EXISTS (SELECT 1 FROM friendships f"
    " WHERE f.user_low_id = LEAST(p.author_id, %(me)s::uuid)"
    " AND f.user_high_id = GREATEST(p.author_id, %(me)s::uuid)))"
)

_FEED = (
    "SELECT p.id::text, p.description, p.image_key, p.created_at,"
    f" {_CURSOR_TEXT} AS cursor_at,"
    " u.id::text, u.full_name, u.profile_image_key,"
    " ARRAY(SELECT pl.normalized_label::text FROM post_labels pl WHERE pl.post_id = p.id"
    " ORDER BY pl.confidence DESC, pl.normalized_label::text ASC),"
    " (SELECT count(*) FROM comments c WHERE c.post_id = p.id AND c.deleted_at IS NULL)::int"
    " FROM posts p JOIN users u ON u.id = p.author_id"
    f" WHERE {_VISIBLE}"
    " AND (%(label)s::text IS NULL OR EXISTS (SELECT 1 FROM post_labels pl"
    " WHERE pl.post_id = p.id AND pl.normalized_label = %(label)s::citext))"
    " AND (%(ts)s::timestamptz IS NULL OR (p.created_at, p.id) < (%(ts)s::timestamptz, %(cid)s::uuid))"
    " ORDER BY p.created_at DESC, p.id DESC"
    " LIMIT %(limit)s"
)

_INSERT_POST = (
    "INSERT INTO posts (author_id, description, image_key) VALUES (%s::uuid, %s, %s)"
    " RETURNING id::text, created_at"
)

_INSERT_LABELS = (
    "INSERT INTO post_labels (post_id, normalized_label, confidence, source_label)"
    " SELECT %(post)s::uuid, x.name, x.confidence, x.source"
    " FROM unnest(%(names)s::text[], %(confidences)s::numeric[], %(sources)s::text[])"
    " AS x(name, confidence, source)"
    " ON CONFLICT (post_id, normalized_label)"
    " DO UPDATE SET confidence = EXCLUDED.confidence, source_label = EXCLUDED.source_label"
)

_LABELS = (
    "SELECT pl.normalized_label::text AS name, count(*)::int AS post_count"
    " FROM posts p JOIN post_labels pl ON pl.post_id = p.id"
    f" WHERE {_VISIBLE}"
    " AND (%(pattern)s::text IS NULL OR pl.normalized_label::text ILIKE %(pattern)s::text)"
    " GROUP BY pl.normalized_label"
    " ORDER BY post_count DESC, name ASC"
)

# Sin fila: la publicación no existe. Con fila: ``visible`` dice si es autor o amigo.
_POST_ACCESS = f"SELECT {_VISIBLE} AS visible FROM posts p WHERE p.id = %(post)s::uuid"

# Solo en la ruta de rechazo de ``_CREATE_COMMENT``: distingue inexistente de no visible.
_POST_EXISTS = "SELECT 1 FROM posts WHERE id = %(post)s::uuid"

_LIST_COMMENTS = (
    "SELECT c.id::text, c.content, c.created_at, u.id::text, u.full_name, u.profile_image_key"
    " FROM comments c JOIN users u ON u.id = c.author_id"
    " WHERE c.post_id = %(post)s::uuid AND c.deleted_at IS NULL"
    " ORDER BY c.created_at ASC, c.id ASC"
)

_CREATE_COMMENT = (
    "WITH target AS (SELECT p.id FROM posts p"
    f" WHERE p.id = %(post)s::uuid AND {_VISIBLE}),"
    " ins AS (INSERT INTO comments (post_id, author_id, content)"
    " SELECT t.id, %(me)s::uuid, %(body)s FROM target t"
    " RETURNING id, content, created_at)"
    " SELECT ins.id::text, ins.content, ins.created_at, u.id::text, u.full_name, u.profile_image_key"
    " FROM ins JOIN users u ON u.id = %(me)s::uuid"
)


def escape_like(text: str) -> str:
    """Escapa ``\\``, ``%`` y ``_`` para usar el texto como literal dentro de ILIKE."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _author(row: Any, offset: int) -> PublicUserRecord:
    return PublicUserRecord(id=row[offset], full_name=row[offset + 1], profile_image_key=row[offset + 2])


def _comment(row: Any) -> CommentRecord:
    return CommentRecord(id=row[0], body=row[1], created_at=row[2], author=_author(row, 3))


def _feed_row(row: Any) -> FeedRow:
    post = PostRecord(
        id=row[0],
        description=row[1],
        image_key=row[2],
        created_at=row[3],
        author=_author(row, 5),
        labels=tuple(row[8]),
        comments_count=row[9],
    )
    return FeedRow(post=post, cursor_at=row[4])


class PostgresPostsRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def list_feed(self, me_id: str, label: str | None, after: CursorPosition | None, limit: int) -> list[FeedRow]:
        params = {
            "me": me_id,
            "label": label,
            "ts": after.created_at if after else None,
            "cid": after.user_id if after else None,
            "limit": limit,
        }
        with self._db.connection() as conn:
            rows = conn.execute(_FEED, params).fetchall()
        return [_feed_row(row) for row in rows]

    def create_post(
        self, author_id: str, image_key: str, description: str | None, labels: Sequence[NormalizedLabel]
    ) -> tuple[str, datetime]:
        with self._db.connection() as conn:
            with conn.transaction():
                row = conn.execute(_INSERT_POST, (author_id, description, image_key)).fetchone()
                if row is None:
                    raise RuntimeError("INSERT posts no devolvió fila")
                if labels:
                    conn.execute(
                        _INSERT_LABELS,
                        {
                            "post": row[0],
                            "names": [label.name for label in labels],
                            "confidences": [label.confidence for label in labels],
                            "sources": [label.source_name for label in labels],
                        },
                    )
        return row[0], row[1]

    def list_labels(self, me_id: str, query: str | None) -> list[LabelCount]:
        pattern = f"%{escape_like(query)}%" if query else None
        with self._db.connection() as conn:
            rows = conn.execute(_LABELS, {"me": me_id, "pattern": pattern}).fetchall()
        return [LabelCount(name=row[0], post_count=row[1]) for row in rows]

    def list_comments(self, me_id: str, post_id: str) -> list[CommentRecord]:
        with self._db.connection() as conn:
            access = conn.execute(_POST_ACCESS, {"me": me_id, "post": post_id}).fetchone()
            if access is None:
                raise PostNotFound()
            if not access[0]:
                raise NotFriendOrAuthor()
            rows = conn.execute(_LIST_COMMENTS, {"post": post_id}).fetchall()
        return [_comment(row) for row in rows]

    def create_comment(self, me_id: str, post_id: str, body: str) -> CommentRecord:
        with self._db.connection() as conn:
            with conn.transaction():
                row = conn.execute(_CREATE_COMMENT, {"me": me_id, "post": post_id, "body": body}).fetchone()
            if row is None:
                # Nada se escribió: ahora se distingue por qué (solo en la ruta de rechazo).
                if conn.execute(_POST_EXISTS, {"post": post_id}).fetchone() is None:
                    raise PostNotFound()
                raise NotFriendOrAuthor()
        return _comment(row)


class UnavailablePostsRepository:
    """Sin RDS configurado: toda consulta responde 503 (nunca memoria)."""

    def list_feed(self, me_id: str, label: str | None, after: CursorPosition | None, limit: int) -> list[FeedRow]:
        raise ServiceUnavailableError()

    def create_post(
        self, author_id: str, image_key: str, description: str | None, labels: Sequence[NormalizedLabel]
    ) -> tuple[str, datetime]:
        raise ServiceUnavailableError()

    def list_labels(self, me_id: str, query: str | None) -> list[LabelCount]:
        raise ServiceUnavailableError()

    def list_comments(self, me_id: str, post_id: str) -> list[CommentRecord]:
        raise ServiceUnavailableError()

    def create_comment(self, me_id: str, post_id: str, body: str) -> CommentRecord:
        raise ServiceUnavailableError()
