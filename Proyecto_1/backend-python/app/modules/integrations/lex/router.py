"""Bot de Facultad con Amazon Lex V2. Pendiente: PRO-19."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.common.auth import require_complete_profile
from app.common.contract import ContractModel, Field
from app.common.errors import NotImplementedApiError

TICKET = "PRO-19"
router = APIRouter(tags=["Bot"], dependencies=[Depends(require_complete_profile)])


class BotMessageRequest(ContractModel):
    text: str = Field(min_length=1, max_length=500)
    sessionId: str = Field(min_length=1, max_length=100)


@router.post("/bot/messages", operation_id="sendBotMessage")
def send_bot_message(body: BotMessageRequest) -> None:
    raise NotImplementedApiError(TICKET, "sendBotMessage")
