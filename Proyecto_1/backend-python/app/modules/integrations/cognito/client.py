"""Cliente boto3 de ``cognito-idp``.

Las operaciones que usa la API son públicas (el modelo de botocore las marca
sin autenticación): boto3 no las firma y no requiere credenciales. Se usa una
sesión propia igual que Translate y Lex.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from app.config import CognitoSettings


def build_cognito_client(settings: CognitoSettings) -> Any:
    config = Config(
        region_name=settings.region,
        connect_timeout=settings.timeout_seconds,
        read_timeout=settings.timeout_seconds,
        # Dos intentos en total (un reintento): el usuario espera la respuesta en línea.
        retries={"mode": "standard", "total_max_attempts": 2},
    )
    return boto3.session.Session().client("cognito-idp", config=config)
