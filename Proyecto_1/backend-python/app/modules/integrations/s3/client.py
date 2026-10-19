"""Cliente boto3 de S3 para HeadObject.

A diferencia de Cognito, S3 sí firma las solicitudes: en EC2 usa el instance
profile ``semisocial-g15-backend-profile`` (``s3:GetObject`` sobre
``Fotos_Perfil/*``). Nunca se leen llaves desde la configuración.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from app.config import S3Settings


def build_s3_client(settings: S3Settings) -> Any:
    config = Config(
        region_name=settings.region,
        connect_timeout=settings.timeout_seconds,
        read_timeout=settings.timeout_seconds,
        retries={"mode": "standard", "total_max_attempts": 2},
    )
    return boto3.session.Session().client("s3", config=config)
