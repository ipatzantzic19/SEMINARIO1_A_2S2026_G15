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

# Fecha y hora ISO 8601 / RFC 3339. La zona se exige después (AwareDatetime) para
# dar un mensaje específico; aquí solo se descartan números y fechas sin hora.
_PATRON_FECHA_HORA = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([Zz]|[+-]\d{2}:?\d{2})?$"
)

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
        # No se aceptan timestamps numéricos ni null: solo texto ISO 8601.
        if not isinstance(valor, str) or not _PATRON_FECHA_HORA.match(valor):
            raise PydanticCustomError(
                "taskflow_fecha_invalida", acuerdos.TRADUCCIONES_VALIDACION["datetime_parsing"]
            )
        return valor


class SolicitudEstadoTarea(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    completada: bool
