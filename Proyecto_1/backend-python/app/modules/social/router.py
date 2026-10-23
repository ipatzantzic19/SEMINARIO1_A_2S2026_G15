"""Usuarios y amistades (PRO-15). Requiere perfil completo (403 si no).

Contrato: docs/api/openapi.yaml; reglas, errores y SQL: docs/api/python-friends.md.
Orden de validación: 401 → 403 → 400 → lógica.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request

from app.common.auth import Principal, require_complete_profile
from app.common.contract import ContractModel, Pagination
from app.modules.social.service import SocialService

router = APIRouter(tags=["Amistades"], dependencies=[Depends(require_complete_profile)])


class CreateFriendRequest(ContractModel):
    addresseeId: UUID


class AnswerFriendRequest(ContractModel):
    decision: Literal["accepted", "rejected"]


def get_social_service(request: Request) -> SocialService:
    return request.app.state.social_service


@router.get("/users", operation_id="listNonFriends")
def list_non_friends(
    page: Annotated[Pagination, Depends()],
    principal: Principal = Depends(require_complete_profile),
    service: SocialService = Depends(get_social_service),
) -> dict:
    return service.list_non_friends(principal, page.cursor, page.limit)


@router.get("/friend-requests", operation_id="listFriendRequests")
def list_friend_requests(
    principal: Principal = Depends(require_complete_profile),
    service: SocialService = Depends(get_social_service),
) -> list[dict]:
    return service.list_requests(principal)


@router.post("/friend-requests", operation_id="createFriendRequest", status_code=201)
def create_friend_request(
    body: CreateFriendRequest,
    principal: Principal = Depends(require_complete_profile),
    service: SocialService = Depends(get_social_service),
) -> dict:
    return service.create_request(principal, body.addresseeId)


@router.patch("/friend-requests/{requestId}", operation_id="answerFriendRequest")
def answer_friend_request(
    requestId: Annotated[UUID, Path()],
    body: AnswerFriendRequest,
    principal: Principal = Depends(require_complete_profile),
    service: SocialService = Depends(get_social_service),
) -> dict:
    return service.answer_request(principal, requestId, body.decision)


@router.get("/friends", operation_id="listFriends")
def list_friends(
    principal: Principal = Depends(require_complete_profile),
    service: SocialService = Depends(get_social_service),
) -> list[dict]:
    return service.list_friends(principal)
