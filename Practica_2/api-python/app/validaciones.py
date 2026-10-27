"""Piezas de validación compartidas entre módulos."""

import re
from typing import Annotated

from fastapi import Path
from pydantic import BeforeValidator
from pydantic_core import PydanticCustomError

from app import acuerdos


def _validar_id_recurso(valor: object) -> object:
    """taskId / fileId: ver PATRON_ID_RECURSO en acuerdos.py.

    Solo decide el formato; el tope BIGINT_MAXIMO lo aplica `Path(le=...)` para
    reportar "Debe ser menor o igual que ...".
    """
    texto = valor if isinstance(valor, str) else ""
    if re.fullmatch(acuerdos.PATRON_ID_RECURSO, texto):
        return int(texto)
    if re.fullmatch(acuerdos.PATRON_ID_NO_POSITIVO, texto):
        raise PydanticCustomError("taskflow_id_minimo", acuerdos.DETALLE_ID_MINIMO)
    raise PydanticCustomError("taskflow_id_no_entero", acuerdos.DETALLE_ID_NO_ENTERO)


IdRecurso = Annotated[int, BeforeValidator(_validar_id_recurso), Path(le=acuerdos.BIGINT_MAXIMO)]


def exigir_texto_no_en_blanco(valor: str) -> str:
    """Rechaza "" y cadenas de solo espacios (los CHECK BTRIM(...) > 0 del esquema)."""
    if not valor.strip():
        raise PydanticCustomError("taskflow_texto_en_blanco", acuerdos.DETALLE_TEXTO_EN_BLANCO)
    return valor
