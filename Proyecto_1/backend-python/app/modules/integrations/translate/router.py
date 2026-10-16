"""Amazon Translate (PRO-18). Destinos v1: es, en, fr, de.

Contrato: ``POST /translations`` en docs/api/openapi.yaml; detalles y
decisiones en docs/api/translation.md.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import field_validator

from app.common.auth import require_complete_profile
from app.common.contract import ContractModel, Field
from app.modules.integrations.translate.service import (
    AUTO,
    MAX_TEXT_BYTES,
    MAX_TEXT_CHARS,
    TranslationService,
)

router = APIRouter(tags=["Traducción"], dependencies=[Depends(require_complete_profile)])

# "auto" o un código de idioma de Translate: "es", "fr", "zh-TW", "fa-AF", ...
_LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class TranslateRequest(ContractModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    sourceLanguage: str = AUTO
    targetLanguage: Literal["es", "en", "fr", "de"]

    @field_validator("text")
    @classmethod
    def _text_within_translate_limits(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El texto no puede estar vacío")
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError:
            raise ValueError("El texto contiene caracteres inválidos") from None
        if size > MAX_TEXT_BYTES:
            raise ValueError(f"El texto supera {MAX_TEXT_BYTES} bytes UTF-8")
        return value

    @field_validator("sourceLanguage")
    @classmethod
    def _source_language_format(cls, value: str) -> str:
        if value != AUTO and not _LANGUAGE_CODE_RE.match(value):
            raise ValueError("sourceLanguage debe ser 'auto' o un código de idioma (p. ej. es, en, zh-TW)")
        return value


class TranslateResponse(ContractModel):
    translatedText: str
    sourceLanguage: str
    targetLanguage: str


def get_translation_service(request: Request) -> TranslationService:
    return request.app.state.translation_service


@router.post("/translations", operation_id="translateText", response_model=TranslateResponse)
def translate_text(
    body: TranslateRequest,
    service: TranslationService = Depends(get_translation_service),
) -> TranslateResponse:
    result = service.translate(body.text, body.sourceLanguage, body.targetLanguage)
    return TranslateResponse(
        translatedText=result.translated_text,
        sourceLanguage=result.source_language,
        targetLanguage=result.target_language,
    )
