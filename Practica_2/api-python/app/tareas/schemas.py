"""Cuerpos de request de tareas según contracts/openapi.yaml.

A diferencia de autenticación, el modelo no es `strict` completo porque
fechaCreacion llega como texto y debe convertirse a datetime; la rigidez de
tipos se aplica campo por campo (`strict=True` en textos y booleanos).
"""

import re
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app import acuerdos
from app.validaciones import exigir_texto_no_en_blanco

Texto = Annotated[str, Field(strict=True)]


class SolicitudTarea(BaseModel):
    """POST y PUT. En PUT, fechaCreacion se acepta pero el servicio la ignora."""

    model_config = ConfigDict(extra="forbid")

    titulo: Annotated[str, Field(strict=True, max_length=200)]
    descripcion: Texto = ""
    fechaCreacion: AwareDatetime | None = None

    @field_validator("titulo")
    @classmethod
    def _titulo_no_en_blanco(cls, valor: str) -> str:
        return exigir_texto_no_en_blanco(valor)

    @field_validator("fechaCreacion", mode="before")
    @classmethod
    def _fecha_iso(cls, valor: object) -> object:
        # Solo texto que cumpla PATRON_FECHA_HORA completo (no números ni null). La zona
        # se exige después con AwareDatetime para dar un mensaje específico.
        if not isinstance(valor, str) or not re.fullmatch(acuerdos.PATRON_FECHA_HORA, valor):
            raise PydanticCustomError(
                "taskflow_fecha_invalida", acuerdos.TRADUCCIONES_VALIDACION["datetime_parsing"]
            )
        return valor


class SolicitudEstadoTarea(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    completada: bool
