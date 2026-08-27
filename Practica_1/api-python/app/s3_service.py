"""Subida de imágenes a S3 y construcción de URLs públicas.

Usa boto3 con la cadena de credenciales por defecto (perfil de instancia
`CloudCinema-Python-S3-PRA3` en EC2; en tests, moto intercepta las llamadas).
Nunca se configuran AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY — el equipo
decidió no usar usuarios IAM personales ni access keys locales (ver
docs/pra-4/ENTREGA_IAM_PERSONAS_2_Y_3.md).

Los prefijos `Fotos_Perfil/`/`Fotos_Peliculas/` van fijos como literales
en cada llamada (no se leen de variables de entorno): así es como
realmente se comporta Node.js hoy (`PREFIJO_FOTOS_PERFIL`/
`PREFIJO_FOTOS_PELICULAS` están declaradas pero nunca se usan en
api-node/src/config/configuration.ts), documentado en
docs/general/arquitectura-decidida.md.
"""

import uuid

import boto3

from app.config import get_settings


def _cliente_s3():
    # Se crea sin cachear para que moto pueda interceptar la llamada en cada test,
    # sin depender de en qué momento se instancia el cliente por primera vez.
    settings = get_settings()
    return boto3.client("s3", region_name=settings.region_aws)


def upload_image(contenido: bytes, nombre_original: str, prefijo: str, content_type: str) -> str:
    """Sube el contenido a S3 y devuelve la clave del objeto (`<prefijo><uuid4>.<ext>`)."""
    extension = nombre_original.rsplit(".", 1)[-1] if "." in nombre_original else "jpg"
    clave = f"{prefijo}{uuid.uuid4()}.{extension}"

    settings = get_settings()
    _cliente_s3().put_object(
        Bucket=settings.bucket_imagenes,
        Key=clave,
        Body=contenido,
        ContentType=content_type,
    )
    return clave


def get_public_url(clave: str) -> str:
    if not clave:
        return ""
    settings = get_settings()
    return f"https://{settings.bucket_imagenes}.s3.{settings.region_aws}.amazonaws.com/{clave}"
