"""Configuración por variables de entorno.

Los nombres coinciden con Practica_2/config/.env.example (DB_HOST, DB_PORT,
...). En desarrollo se cargan además desde api-python/.env mediante
python-dotenv; las variables reales del proceso tienen prioridad.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import acuerdos

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "taskflow"
    db_user: str
    db_password: str
    db_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "verify-full"
    db_sslrootcert: str | None = None

    port: int = 8000

    jwt_secret: str = Field(min_length=1)
    jwt_expires_in: int = Field(default=acuerdos.JWT_EXPIRACION_POR_DEFECTO, gt=0)

    # Lista separada por comas; vacía = sin CORS.
    cors_origins: str = ""

    @field_validator("db_sslrootcert", mode="before")
    @classmethod
    def _vacio_a_none(cls, valor):
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor

    @property
    def lista_cors(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origins.split(",") if origen.strip()]


@lru_cache
def obtener_config() -> Configuracion:
    return Configuracion()
