"""Tipos reutilizables derivados de docs/api/openapi.yaml.

Decisiones (documentadas en docs/api/python.md):
- Los límites siguen el OpenAPI aunque la BD permita más (p. ej. comentario 1000).
- Campos adicionales en el cuerpo se ignoran (el OpenAPI no declara
  ``additionalProperties: false``); Node los rechaza con 400.
- ``\\d`` del OpenAPI se interpreta como ``[0-9]`` (solo ASCII).
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import Query
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("Correo electrónico inválido")
    return value


Email = Annotated[str, AfterValidator(_normalize_email)]
Dpi = Annotated[str, StringConstraints(pattern=r"^[0-9]{13}$")]
FullName = Annotated[str, StringConstraints(min_length=2, max_length=160)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=False)


class Pagination:
    """Parámetros ``cursor`` y ``limit`` (1..50, por defecto 20)."""

    def __init__(
        self,
        cursor: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
    ) -> None:
        self.cursor = cursor
        self.limit = limit


__all__ = ["ContractModel", "Dpi", "Email", "Field", "FullName", "Pagination"]
