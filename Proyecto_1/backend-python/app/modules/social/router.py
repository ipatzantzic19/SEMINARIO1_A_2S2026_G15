"""Usuarios y amistades. Pendiente: PRO-15. Requiere perfil completo (403 si no)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from app.common.auth import require_complete_profile
from app.common.contract import ContractModel, Pagination
from app.common.errors import NotImplementedApiError

TICKET = "PRO-15"
router = APIRouter(tags=["Amistades"], dependencies=[Depends(require_complete_profile)])


class CreateFriendRequest(ContractModel):
    addresseeId: UUID


class AnswerFriendRequest(ContractModel):
    decision: Literal["accepted", "rejected"]


@router.get("/users", operation_id="listNonFriends")
def list_non_friends(page: Annotated[Pagination, Depends()]) -> None:
    raise NotImplementedApiError(TICKET, "listNonFriends")


@router.get("/friend-requests", operation_id="listFriendRequests")
def list_friend_requests() -> None:
    raise NotImplementedApiError(TICKET, "listFriendRequests")


@router.post("/friend-requests", operation_id="createFriendRequest", status_code=201)
def create_friend_request(body: CreateFriendRequest) -> None:
    raise NotImplementedApiError(TICKET, "createFriendRequest")


@router.patch("/friend-requests/{requestId}", operation_id="answerFriendRequest")
def answer_friend_request(requestId: Annotated[UUID, Path()], body: AnswerFriendRequest) -> None:
    raise NotImplementedApiError(TICKET, "answerFriendRequest")


@router.get("/friends", operation_id="listFriends")
def list_friends() -> None:
    raise NotImplementedApiError(TICKET, "listFriends")
