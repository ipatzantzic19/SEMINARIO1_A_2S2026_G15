"""Publicaciones, comentarios y etiquetas (PRO-34). Requiere perfil completo (403 si no).

Contrato: docs/api/openapi.yaml; reglas, errores y SQL: docs/api/python-posts.md.
Orden de validación: 401 → 403 → 400 → lógica. Las etiquetas se generan con
Rekognition (app/modules/integrations/rekognition).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import AfterValidator

from app.common.auth import Principal, require_complete_profile
from app.common.contract import ContractModel, Field, MultilineText, Pagination
from app.modules.posts.service import PostsService

router = APIRouter(tags=["Publicaciones"], dependencies=[Depends(require_complete_profile)])

def _trimmed(limit: int) -> Callable[[str], str]:
    """Recorta espacios y valida DESPUÉS: vacío o solo espacios es 400, y el límite
    (del OpenAPI) se mide sobre el texto recortado. ``StringConstraints`` no sirve
    aquí: comprueba ``min_length`` antes de recortar y dejaba pasar "   "."""

    def validate(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("No puede estar vacío")
        if len(value) > limit:
            raise ValueError(f"Máximo {limit} caracteres")
        return value

    return validate


Description = Annotated[MultilineText, AfterValidator(_trimmed(2000))]
CommentBody = Annotated[MultilineText, AfterValidator(_trimmed(1000))]


class CreatePostRequest(ContractModel):
    imageKey: str = Field(min_length=1, max_length=1024)
    description: Description | None = None


class CreateCommentRequest(ContractModel):
    body: CommentBody


def get_posts_service(request: Request) -> PostsService:
    return request.app.state.posts_service


@router.get("/posts", operation_id="getFeed")
def get_feed(
    page: Annotated[Pagination, Depends()],
    label: Annotated[str | None, Query()] = None,
    principal: Principal = Depends(require_complete_profile),
    service: PostsService = Depends(get_posts_service),
) -> dict:
    return service.feed(principal, label, page.cursor, page.limit)


@router.post("/posts", operation_id="createPost", status_code=201)
def create_post(
    body: CreatePostRequest,
    principal: Principal = Depends(require_complete_profile),
    service: PostsService = Depends(get_posts_service),
) -> dict:
    return service.create(principal, body.imageKey, body.description)


@router.get("/posts/{postId}/comments", operation_id="listComments")
def list_comments(
    postId: Annotated[UUID, Path()],
    principal: Principal = Depends(require_complete_profile),
    service: PostsService = Depends(get_posts_service),
) -> list[dict]:
    return service.list_comments(principal, postId)


@router.post("/posts/{postId}/comments", operation_id="createComment", status_code=201)
def create_comment(
    postId: Annotated[UUID, Path()],
    body: CreateCommentRequest,
    principal: Principal = Depends(require_complete_profile),
    service: PostsService = Depends(get_posts_service),
) -> dict:
    return service.create_comment(principal, postId, body.body)


@router.get("/labels", operation_id="listVisibleLabels")
def list_visible_labels(
    q: Annotated[str | None, Query()] = None,
    principal: Principal = Depends(require_complete_profile),
    service: PostsService = Depends(get_posts_service),
) -> list[dict]:
    return service.labels(principal, q)
