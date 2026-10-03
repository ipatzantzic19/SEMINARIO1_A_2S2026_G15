"""Cuerpos de request de autenticación según contracts/openapi.yaml.

- `extra="forbid"` implementa `additionalProperties: false`.
- `strict=True` evita coerciones silenciosas (por ejemplo, un número como nombre).
- nombreUsuario y correoElectronico se normalizan (trim + minúsculas) ANTES de validar.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from app import acuerdos
from app.validaciones import PATRON_URL_HTTPS

PATRON_NOMBRE_USUARIO = r"^[a-z0-9_]+$"
# Validación pragmática de `format: email`: algo@dominio.tld, sin espacios.
PATRON_CORREO = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


def _normalizar_identificador(valor: object) -> object:
    return valor.strip().lower() if isinstance(valor, str) else valor


class SolicitudRegistro(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    nombreUsuario: Annotated[str, Field(min_length=3, max_length=50, pattern=PATRON_NOMBRE_USUARIO)]
    correoElectronico: Annotated[str, Field(max_length=254, pattern=PATRON_CORREO)]
    contrasena: Annotated[str, Field(min_length=8, max_length=72)]
    confirmacionContrasena: Annotated[str, Field(min_length=8, max_length=72)]
    urlImagenPerfil: Annotated[str, Field(pattern=PATRON_URL_HTTPS)] | None = None

    @field_validator("nombreUsuario", "correoElectronico", mode="before")
    @classmethod
    def _normalizar(cls, valor: object) -> object:
        return _normalizar_identificador(valor)

    @field_validator("confirmacionContrasena")
    @classmethod
    def _confirmacion_coincide(cls, valor: str, info: ValidationInfo) -> str:
        contrasena = info.data.get("contrasena")
        # Si `contrasena` ya falló su propia validación no se reporta un segundo error.
        if contrasena is not None and valor != contrasena:
            raise PydanticCustomError("taskflow_contrasenas_no_coinciden", acuerdos.DETALLE_CONTRASENAS_NO_COINCIDEN)
        return valor

    @field_validator("urlImagenPerfil", mode="before")
    @classmethod
    def _url_no_nula(cls, valor: object) -> object:
        # El contrato la define como string opcional, no nullable: se omite o se envía texto.
        if valor is None:
            raise PydanticCustomError("taskflow_url_nula", acuerdos.TRADUCCIONES_VALIDACION["string_type"])
        return valor


class SolicitudInicioSesion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    nombreUsuario: str
    contrasena: str

    @field_validator("nombreUsuario", mode="before")
    @classmethod
    def _normalizar(cls, valor: object) -> object:
        return _normalizar_identificador(valor)
