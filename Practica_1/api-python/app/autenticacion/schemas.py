"""DTOs de entrada. Mismos nombres de campo y restricciones de longitud que
api-node/src/autenticacion/dto/autenticacion.dto.ts, documentadas también en
docs/pra-1/CONTRATO_API.md."""

from pydantic import BaseModel, EmailStr, Field


class RegistroForm(BaseModel):
    correoElectronico: EmailStr = Field(min_length=4, max_length=254)
    nombreCompleto: str = Field(min_length=1, max_length=150)
    contrasena: str = Field(min_length=6, max_length=72)
    confirmacionContrasena: str = Field(min_length=6, max_length=72)


class InicioSesionRequest(BaseModel):
    correoElectronico: EmailStr = Field(min_length=4, max_length=254)
    contrasena: str = Field(min_length=6, max_length=72)
