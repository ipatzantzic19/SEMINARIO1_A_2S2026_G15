"""Historial REST del chat (PRO-16). El WebSocket está en ``websocket.py``.

Contrato: docs/api/openapi.yaml (``listMessages``); decisiones y diferencias con
Node en docs/api/python-chat.md. Orden de validación: 401 → 403 → 400 → lógica.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request

from app.common.auth import Principal, require_complete_profile
from app.modules.chat.service import DEFAULT_HISTORY_LIMIT, ChatService

router = APIRouter(tags=["Chat"], dependencies=[Depends(require_complete_profile)])


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.get("/conversations/{friendId}/messages", operation_id="listMessages")
def list_messages(
    friendId: Annotated[UUID, Path()],
    cursor: Annotated[str | None, Query()] = None,
    # Node usa 50 por defecto (el OpenAPI declara 20); el máximo es 50 en ambos.
    limit: Annotated[int, Query(ge=1, le=50)] = DEFAULT_HISTORY_LIMIT,
    principal: Principal = Depends(require_complete_profile),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return service.history(principal.sub, friendId, cursor, limit)
