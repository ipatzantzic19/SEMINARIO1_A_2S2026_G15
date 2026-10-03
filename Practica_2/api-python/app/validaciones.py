"""Piezas de validación compartidas entre módulos."""

from typing import Annotated

from fastapi import Path
from pydantic_core import PydanticCustomError

from app import acuerdos

# `format: uri` con https obligatorio (CHECK ^https:// en schema.sql), sin espacios.
PATRON_URL_HTTPS = r"^https://\S+$"

# taskId / fileId: entero >= 1 dentro del rango BIGINT; si no, 400 ERROR_VALIDACION.
IdRecurso = Annotated[int, Path(ge=acuerdos.ID_MINIMO, le=acuerdos.ID_MAXIMO)]


def exigir_texto_no_en_blanco(valor: str) -> str:
    """Rechaza "" y cadenas de solo espacios (los CHECK BTRIM(...) > 0 del esquema)."""
    if not valor.strip():
        raise PydanticCustomError("taskflow_texto_en_blanco", acuerdos.DETALLE_TEXTO_EN_BLANCO)
    return valor
