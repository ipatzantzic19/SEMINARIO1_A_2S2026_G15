"""Cuerpo de request para registrar metadatos de un objeto ya cargado en S3 o Blob.

Solo se valida el formato; no se comprueba el prefijo de claveObjeto ni que el
objeto exista en el proveedor.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import acuerdos
from app.acuerdos import PATRON_URL_HTTPS
from app.validaciones import exigir_texto_no_en_blanco


class SolicitudArchivo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    nombreOriginal: Annotated[str, Field(max_length=255)]
    tipoMime: Annotated[str, Field(max_length=255)]
    tamanoBytes: Annotated[int, Field(ge=0, le=acuerdos.BIGINT_MAXIMO)]
    proveedorAlmacenamiento: Literal["S3", "BLOB"]
    claveObjeto: str
    urlObjeto: Annotated[str, Field(pattern=PATRON_URL_HTTPS)]

    @field_validator("nombreOriginal", "tipoMime", "claveObjeto")
    @classmethod
    def _no_en_blanco(cls, valor: str) -> str:
        # Los CHECK BTRIM(...) > 0 del esquema darían un 500; se rechazan antes con 400.
        return exigir_texto_no_en_blanco(valor)
