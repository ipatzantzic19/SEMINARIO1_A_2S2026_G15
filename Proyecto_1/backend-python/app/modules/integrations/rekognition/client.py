"""Cliente boto3 de Amazon Rekognition.

Las credenciales salen de la cadena por defecto de boto3: instance profile
``semisocial-g15-backend-role`` en EC2 o el perfil/SSO del desarrollador en
local. Nunca se leen llaves desde la configuración de la API.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from app.config import RekognitionSettings


def build_rekognition_client(settings: RekognitionSettings) -> Any:
    config = Config(
        region_name=settings.region,
        connect_timeout=settings.timeout_seconds,
        read_timeout=settings.timeout_seconds,
        # Un solo intento por llamada: los reintentos (250 ms y 750 ms, igual que
        # Node) los hace LabelDetector; con los de boto se multiplicarían.
        retries={"mode": "standard", "total_max_attempts": 1},
    )
    # Sesión propia (no boto3.DEFAULT_SESSION): la cadena de credenciales se
    # resuelve al crear el cliente con el entorno de ese momento.
    return boto3.session.Session().client("rekognition", config=config)
