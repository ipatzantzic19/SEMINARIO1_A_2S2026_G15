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
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Ni Starlette ni pydantic rechazan estos caracteres: json.loads acepta
# "\u0000" y "\ud800" (también bytes CESU, con surrogatepass). Con NUL, psycopg
# lanza DataError; con un surrogate suelto, UnicodeEncodeError. Ambos
# terminaban en 503, y en el registro DESPUÉS de SignUp (usuario huérfano).
# Un par válido (emoji) ya llega combinado: todo surrogate restante está suelto.
_CONTROL_OR_SURROGATE_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\ud800-\udfff]")  # C0, DEL, C1
_NUL_OR_SURROGATE_RE = re.compile(r"[\x00\ud800-\udfff]")


def _reject_control(value: object) -> object:
    if isinstance(value, str) and _CONTROL_OR_SURROGATE_RE.search(value):
        raise ValueError("Contiene caracteres de control o no válidos")
    return value


def _reject_nul_or_surrogate(value: object) -> object:
    # Contraseñas: solo NUL y surrogates sueltos; los símbolos los decide Cognito.
    if isinstance(value, str) and _NUL_OR_SURROGATE_RE.search(value):
        raise ValueError("Contiene caracteres no válidos")
    return value


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("Correo electrónico inválido")
    return value


# BeforeValidator: el rechazo ocurre antes de recortar espacios (un "\n" final
# también se rechaza) y antes de que el valor llegue a Cognito o a RDS.
PlainText = Annotated[str, BeforeValidator(_reject_control)]
Password = Annotated[str, BeforeValidator(_reject_nul_or_surrogate)]
Email = Annotated[str, AfterValidator(_normalize_email), BeforeValidator(_reject_control)]
Dpi = Annotated[str, StringConstraints(pattern=r"^[0-9]{13}$")]
# Se recortan espacios: users.full_name exige btrim(full_name) <> ''.
FullName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160), BeforeValidator(_reject_control)
]


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


__all__ = ["ContractModel", "Dpi", "Email", "Field", "FullName", "Pagination", "Password", "PlainText"]
