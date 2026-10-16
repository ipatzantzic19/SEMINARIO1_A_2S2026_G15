"""Cliente boto3 de Amazon Translate.

Las credenciales salen de la cadena por defecto de boto3: instance profile
``semisocial-g15-backend-profile`` en EC2 o el perfil/SSO del desarrollador en
local. Nunca se leen llaves desde la configuración de la API.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from app.config import TranslateSettings


def build_translate_client(settings: TranslateSettings) -> Any:
    config = Config(
        region_name=settings.region,
        connect_timeout=settings.timeout_seconds,
        read_timeout=settings.timeout_seconds,
        # Dos intentos en total (un reintento): el usuario espera la respuesta en línea.
        retries={"mode": "standard", "total_max_attempts": 2},
    )
    # Sesión propia (no boto3.DEFAULT_SESSION): la cadena de credenciales se
    # resuelve al crear el cliente con el entorno de ese momento.
    return boto3.session.Session().client("translate", config=config)
