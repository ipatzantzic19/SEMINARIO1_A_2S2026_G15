"""Bot de Facultad con Amazon Lex V2 (PRO-19).

Contrato: ``POST /bot/messages`` en docs/api/openapi.yaml; detalles y
decisiones en docs/api/bot.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import field_validator

from app.common.auth import Principal, require_complete_profile
from app.common.contract import ContractModel, Field
from app.modules.integrations.lex.service import BotService

router = APIRouter(tags=["Bot"])


class BotMessageRequest(ContractModel):
    text: str = Field(min_length=1, max_length=500)
    sessionId: str = Field(min_length=1, max_length=100)

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El texto no puede estar vacío")
        return value


class BotMessageResponse(ContractModel):
    messages: list[str]
    sessionId: str


def get_bot_service(request: Request) -> BotService:
    return request.app.state.bot_service


@router.post("/bot/messages", operation_id="sendBotMessage", response_model=BotMessageResponse)
def send_bot_message(
    body: BotMessageRequest,
    principal: Principal = Depends(require_complete_profile),
    service: BotService = Depends(get_bot_service),
) -> BotMessageResponse:
    messages = service.send(principal.sub, body.sessionId, body.text)
    # Se devuelve el sessionId del cliente sin cambios; el derivado solo lo ve Lex.
    return BotMessageResponse(messages=messages, sessionId=body.sessionId)
