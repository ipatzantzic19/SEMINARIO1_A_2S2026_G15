"""Publicaciones, comentarios y etiquetas. Pendiente: PRO-34.

Las etiquetas se generan con Rekognition (app/modules/integrations/rekognition).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.common.auth import require_complete_profile
from app.common.contract import ContractModel, Field, Pagination
from app.common.errors import NotImplementedApiError

TICKET = "PRO-34"
router = APIRouter(tags=["Publicaciones"], dependencies=[Depends(require_complete_profile)])


class CreatePostRequest(ContractModel):
    imageKey: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=2000)


class CreateCommentRequest(ContractModel):
    body: str = Field(min_length=1, max_length=1000)


@router.get("/posts", operation_id="getFeed")
def get_feed(page: Annotated[Pagination, Depends()], label: Annotated[str | None, Query()] = None) -> None:
    raise NotImplementedApiError(TICKET, "getFeed")


@router.post("/posts", operation_id="createPost", status_code=201)
def create_post(body: CreatePostRequest) -> None:
    raise NotImplementedApiError(TICKET, "createPost")


@router.get("/posts/{postId}/comments", operation_id="listComments")
def list_comments(postId: Annotated[UUID, Path()]) -> None:
    raise NotImplementedApiError(TICKET, "listComments")


@router.post("/posts/{postId}/comments", operation_id="createComment", status_code=201)
def create_comment(postId: Annotated[UUID, Path()], body: CreateCommentRequest) -> None:
    raise NotImplementedApiError(TICKET, "createComment")


@router.get("/labels", operation_id="listVisibleLabels")
def list_visible_labels(q: Annotated[str | None, Query()] = None) -> None:
    raise NotImplementedApiError(TICKET, "listVisibleLabels")
