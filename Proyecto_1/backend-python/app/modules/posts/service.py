"""Publicaciones, feed, comentarios y etiquetas (PRO-34).

Reglas y códigos: docs/api/python-posts.md §3. Resumen:

- Todas las rutas exigen perfil completo (``require_complete_profile`` en el router).
- La identidad sale del ``sub`` del token; el cliente nunca elige el autor.
- ``POST /posts``: la clave debe tener el formato de la Lambda de carga, pertenecer
  al ``sub`` del token (403) y existir como JPEG/PNG en S3 (404/400). DetectLabels
  se invoca antes de tocar RDS: si falla (429/503) no se guarda nada. Sin etiquetas
  calificadas la publicación se guarda sin etiquetas (no se inventa "general").
- Comentarios: una publicación inexistente es 404; una que existe pero cuyo autor no
  es el usuario ni su amigo es 403 ``NOT_FRIEND_OR_AUTHOR`` (igual que Node y el OpenAPI).
- Logs sin PII: solo evento, motivo y conteos; nunca ids, claves, textos ni etiquetas.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import UUID

from app.common.auth import Principal
from app.common.errors import ApiError, ForbiddenError, ServiceUnavailableError
from app.config import S3Settings
from app.modules.integrations.rekognition.labels import normalize_filter
from app.modules.posts.repository import (
    CommentRecord,
    FeedRow,
    NotFriendOrAuthor,
    PostNotFound,
    PostRecord,
    PostsRepository,
)
from app.modules.social.cursor import InvalidCursor, decode_cursor, encode_cursor
from app.modules.social.repository import PublicUserRecord
from app.modules.users.directory import UserDirectory, log_event

T = TypeVar("T")

# Rekognition DetectLabels solo acepta JPEG y PNG; la Lambda también guarda WebP.
POST_MIME_TYPES = ("image/jpeg", "image/png")
MAX_FILTER_CHARS = 100

# Nombre de archivo que genera la Lambda: randomUUID() + extensión por MIME
# (lambdas/image-upload/index.js y multipart.js getExtensionForMime).
_FILE_NAME = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:jpg|png|webp)"
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _error(status: int, code: str, message: str, reason: str | None = None) -> ApiError:
    return ApiError(status, code, message, details={"reason": reason} if reason else None)


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Publicación no encontrada.")


def _not_friend_or_author() -> ApiError:
    return ForbiddenError(
        "Solo el autor de la publicación y sus amigos pueden ver y escribir comentarios.",
        details={"reason": "NOT_FRIEND_OR_AUTHOR"},
    )


def iso_millis(moment: datetime) -> str:
    """Igual que Date.toISOString() de Node: milisegundos truncados y "Z"."""
    utc = moment.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


class PostsService:
    def __init__(
        self,
        directory: UserDirectory,
        posts: PostsRepository,
        images: Any,
        detector: Any,
        s3: S3Settings,
    ) -> None:
        self._directory = directory
        self._users = directory.users
        self._posts = posts
        self._images = images
        self._detector = detector
        self._key_re = re.compile(rf"{re.escape(s3.posts_prefix)}(?P<sub>[^/]+)/{_FILE_NAME}")

    def _call(self, operation: Callable[[], T]) -> T:
        """Deja pasar errores de negocio; cualquier otra falla de RDS es 503 (sin memoria)."""
        try:
            return operation()
        except (ApiError, PostNotFound, NotFriendOrAuthor):
            raise
        except Exception as exc:  # noqa: BLE001
            # psycopg/pool: el mensaje puede contener datos de conexión; solo el tipo.
            log_event("posts.db_error", logging.ERROR, errorType=type(exc).__name__)
            raise ServiceUnavailableError() from None

    def _me(self, principal: Principal) -> PublicUserRecord:
        record = self._directory.call(lambda: self._users.get_by_sub(principal.sub))
        if record is None or not record.profile_complete:
            # No ocurre tras require_complete_profile salvo una carrera con RDS.
            raise ForbiddenError(
                "Complete su perfil para usar esta funcionalidad.", details={"reason": "PROFILE_INCOMPLETE"}
            )
        return PublicUserRecord(id=record.id, full_name=record.full_name, profile_image_key=record.profile_image_key)

    # -- Formato de respuesta ---------------------------------------------

    def _public_user(self, user: PublicUserRecord) -> dict[str, Any]:
        return {
            "userId": user.id,
            "fullName": user.full_name,
            "profileImageUrl": self._directory.image_url(user.profile_image_key),
        }

    def _post(self, post: PostRecord) -> dict[str, Any]:
        return {
            "postId": post.id,
            "author": self._public_user(post.author),
            "imageUrl": self._directory.image_url(post.image_key),
            "description": post.description,
            "labels": list(post.labels),
            "commentsCount": post.comments_count,
            "createdAt": iso_millis(post.created_at),
        }

    def _comment(self, comment: CommentRecord) -> dict[str, Any]:
        return {
            "commentId": comment.id,
            "author": self._public_user(comment.author),
            "body": comment.body,
            "createdAt": iso_millis(comment.created_at),
        }

    # -- GET /posts -------------------------------------------------------------

    def feed(self, principal: Principal, label: str | None, cursor: str | None, limit: int) -> dict[str, Any]:
        after = None
        if cursor is not None:
            try:
                after = decode_cursor(cursor)
            except InvalidCursor:
                raise _error(400, "VALIDATION_ERROR", "El cursor no es válido.", "INVALID_CURSOR") from None
        wanted = self._clean_filter(label, "INVALID_LABEL")
        me = self._me(principal)
        rows: list[FeedRow] = self._call(lambda: self._posts.list_feed(me.id, wanted, after, limit + 1))
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1]
            next_cursor = encode_cursor(last.cursor_at, last.post.id)
        return {"items": [self._post(row.post) for row in page], "nextCursor": next_cursor}

    # -- POST /posts ------------------------------------------------------------

    def create(self, principal: Principal, image_key: str, description: str | None) -> dict[str, Any]:
        me = self._me(principal)
        # fullmatch: ``$`` aceptaría un salto de línea final.
        match = self._key_re.fullmatch(image_key)
        if match is None:
            raise _error(400, "VALIDATION_ERROR", "La clave de la imagen no es válida.", "INVALID_IMAGE_KEY")
        if match["sub"] != principal.sub:
            raise ForbiddenError("La imagen no pertenece a su cuenta.", details={"reason": "IMAGE_NOT_OWNED"})

        info = self._images.head(image_key)
        if info is None:
            raise _error(404, "NOT_FOUND", "No se encontró la imagen cargada.", "IMAGE_NOT_FOUND")
        if info.content_type not in POST_MIME_TYPES:
            raise _error(400, "VALIDATION_ERROR", "La imagen debe ser JPEG o PNG.", "IMAGE_UNSUPPORTED")

        # Rekognition antes de RDS: si falla (429/503), no se guarda nada.
        labels = self._detector.detect(image_key)
        post_id, created_at = self._call(lambda: self._posts.create_post(me.id, image_key, description, labels))
        log_event("posts.created", labelCount=len(labels))
        return self._post(
            PostRecord(
                id=post_id,
                author=me,
                description=description,
                image_key=image_key,
                labels=tuple(label.name for label in labels),
                comments_count=0,
                created_at=created_at,
            )
        )

    # -- GET /labels ------------------------------------------------------------

    def labels(self, principal: Principal, query: str | None) -> list[dict[str, Any]]:
        wanted = self._clean_filter(query, "INVALID_QUERY")
        me = self._me(principal)
        rows = self._call(lambda: self._posts.list_labels(me.id, wanted))
        return [{"name": row.name, "postCount": row.post_count} for row in rows]

    # -- GET/POST /posts/{postId}/comments ----------------------------------------

    def list_comments(self, principal: Principal, post_id: UUID) -> list[dict[str, Any]]:
        me = self._me(principal)
        try:
            comments = self._call(lambda: self._posts.list_comments(me.id, str(post_id)))
        except PostNotFound:
            raise _not_found() from None
        except NotFriendOrAuthor:
            raise _not_friend_or_author() from None
        return [self._comment(comment) for comment in comments]

    def create_comment(self, principal: Principal, post_id: UUID, body: str) -> dict[str, Any]:
        me = self._me(principal)
        try:
            comment = self._call(lambda: self._posts.create_comment(me.id, str(post_id), body))
        except PostNotFound:
            raise _not_found() from None
        except NotFriendOrAuthor:
            raise _not_friend_or_author() from None
        log_event("posts.comment_created")
        return self._comment(comment)

    # -- auxiliares -------------------------------------------------------------

    @staticmethod
    def _clean_filter(value: str | None, reason: str) -> str | None:
        """Recorta y normaliza (trim, NFC, minúsculas); vacío = sin filtro; demasiado largo = 400."""
        if value is None:
            return None
        cleaned = normalize_filter(value)
        if len(cleaned) > MAX_FILTER_CHARS or _CONTROL_RE.search(cleaned):
            raise _error(400, "VALIDATION_ERROR", "El filtro no es válido.", reason)
        return cleaned or None
