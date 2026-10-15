"""Amazon Translate. Pendiente: PRO-18. Destinos v1: es, en, fr, de."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from app.common.auth import require_complete_profile
from app.common.contract import ContractModel, Field
from app.common.errors import NotImplementedApiError

TICKET = "PRO-18"
SUPPORTED_TARGETS = ("es", "en", "fr", "de")
router = APIRouter(tags=["Traducción"], dependencies=[Depends(require_complete_profile)])


class TranslateRequest(ContractModel):
    text: str = Field(min_length=1, max_length=5000)
    sourceLanguage: str = "auto"
    targetLanguage: Literal["es", "en", "fr", "de"]


@router.post("/translations", operation_id="translateText")
def translate_text(body: TranslateRequest) -> None:
    raise NotImplementedApiError(TICKET, "translateText")
