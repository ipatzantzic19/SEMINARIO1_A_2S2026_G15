"""Credencial RS256 exclusiva para subir una captura del reto facial indicado."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.common.errors import ApiError

FACE_UPLOAD_ISSUER = "semisocial-face-auth"
FACE_UPLOAD_AUDIENCE = "semisocial-image-upload"


class FaceUploadTokenSigner:
    def __init__(self, private_key_file: str | None, key_id: str | None) -> None:
        self._private_key_file = private_key_file
        self._key_id = key_id

    def issue(self, challenge_id: str, issued_at: int, ttl_seconds: int) -> str:
        try:
            if not self._private_key_file or not self._key_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self._key_id):
                raise ValueError("Configuración de firma incompleta")
            if not challenge_id or type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 300:
                raise ValueError("Reto o vigencia no válidos")
            key = serialization.load_pem_private_key(Path(self._private_key_file).read_bytes(), password=None)
            if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
                raise ValueError("Se requiere una clave RSA de al menos 2048 bits")
            return jwt.encode(
                {
                    "iss": FACE_UPLOAD_ISSUER, "aud": FACE_UPLOAD_AUDIENCE,
                    "purpose": "faceCapture", "challengeId": challenge_id,
                    "iat": issued_at, "exp": issued_at + ttl_seconds, "jti": str(uuid.uuid4()),
                },
                key, algorithm="RS256", headers={"typ": "JWT", "kid": self._key_id},
            )
        except Exception:
            # No revelar rutas, llaves ni detalles del error criptográfico.
            raise ApiError(503, "SERVICE_UNAVAILABLE") from None
