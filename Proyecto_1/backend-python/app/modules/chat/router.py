"""Chat entre amigos. Pendiente: PRO-16.

Historial REST por cursor. El WebSocket (mismo JWT, LISTEN/NOTIFY entre
instancias) aún no tiene URL ni formato de eventos en el contrato.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from app.common.auth import require_complete_profile
from app.common.contract import Pagination
from app.common.errors import NotImplementedApiError

TICKET = "PRO-16"
router = APIRouter(tags=["Chat"], dependencies=[Depends(require_complete_profile)])


@router.get("/conversations/{friendId}/messages", operation_id="listMessages")
def list_messages(friendId: Annotated[UUID, Path()], page: Annotated[Pagination, Depends()]) -> None:
    raise NotImplementedApiError(TICKET, "listMessages")
