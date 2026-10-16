"""Cliente boto3 de Amazon Lex V2 Runtime (``lexv2-runtime``).

Igual que Translate: cadena de credenciales por defecto (instance profile en
EC2, perfil/SSO en local) y sesión propia, nunca llaves en la configuración.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from app.config import LexSettings


def build_lex_client(settings: LexSettings) -> Any:
    config = Config(
        region_name=settings.region,
        connect_timeout=settings.timeout_seconds,
        read_timeout=settings.timeout_seconds,
        # Dos intentos en total (un reintento): el usuario espera la respuesta en línea.
        retries={"mode": "standard", "total_max_attempts": 2},
    )
    return boto3.session.Session().client("lexv2-runtime", config=config)
