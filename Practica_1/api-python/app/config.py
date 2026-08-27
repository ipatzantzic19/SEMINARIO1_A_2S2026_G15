"""Configuración leída de variables de entorno.

Los nombres de las variables de conexión a la base de datos siguen
exactamente `config/.env.python.example` (prefijo BD_*), que es la
fuente de verdad acordada para el backend Python — no los nombres
sugeridos anteriormente en documentos de entrega (HOST_BD, etc.). La fuente
vigente está en docs/infrastructure.md.

`secreto_jwt` no tiene valor por defecto a propósito: si SECRETO_JWT no
está definido, pydantic-settings lanza un error de validación y el
servidor no arranca. Node.js sí tiene un valor por defecto hardcodeado
('default_secret') cuando falta esa variable — está señalado como un
problema de seguridad en docs/api/node-api-conformance.md y aquí no se replica.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bd_host: str = Field(validation_alias="BD_HOST")
    bd_puerto: int = Field(default=5432, validation_alias="BD_PUERTO")
    bd_nombre: str = Field(default="cloudcinema", validation_alias="BD_NOMBRE")
    bd_usuario: str = Field(default="usuario_cloudcinema_python", validation_alias="BD_USUARIO")
    bd_contrasena: str = Field(validation_alias="BD_CONTRASENA")
    bd_ssl_modo: str = Field(default="verify-full", validation_alias="BD_SSL_MODO")
    bd_certificado_ca: str = Field(default="/etc/ssl/certs/rds-global-bundle.pem", validation_alias="BD_CERTIFICADO_CA")

    region_aws: str = Field(default="us-east-1", validation_alias="REGION_AWS")
    bucket_imagenes: str = Field(default="practica1-images-g15", validation_alias="BUCKET_IMAGENES")

    secreto_jwt: str = Field(validation_alias="SECRETO_JWT")

    puerto: int = Field(default=8000, validation_alias="PORT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
