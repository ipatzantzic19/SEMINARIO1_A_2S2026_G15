"""DTO de entrada para PUT /perfil. Mismas reglas que
api-node/src/perfil/dto/perfil.dto.ts (`ActualizarPerfilDto`): `contrasenaActual`
obligatorio y no vacío pero sin límite de longitud (a diferencia de los DTOs
de contraseña de registro/login, que sí exigen 6-72 caracteres); `nombreCompleto`
opcional, 1 a 150 caracteres cuando se envía."""

from pydantic import BaseModel, Field


class ActualizarPerfilForm(BaseModel):
    contrasenaActual: str = Field(min_length=1)
    nombreCompleto: str | None = Field(default=None, min_length=1, max_length=150)
