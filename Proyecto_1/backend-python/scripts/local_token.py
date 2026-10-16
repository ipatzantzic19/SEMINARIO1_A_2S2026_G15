"""Emite un access token LOCAL con forma de Cognito, firmado con una llave
RSA de desarrollo (``.local/``, ignorada por Git).

Solo sirve con APP_ENV=local y AUTH_LOCAL_PUBLIC_KEY_FILE apuntando a la llave
pública generada. Producción valida contra el JWKS real de Cognito y rechaza
estos tokens.

Uso:  python scripts/local_token.py [--sub <uuid>] [--minutes 60]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DIR = BASE_DIR / ".local"
PRIVATE_KEY = LOCAL_DIR / "jwt-private.pem"
PUBLIC_KEY = LOCAL_DIR / "jwt-public.pem"


def ensure_keys() -> bytes:
    if not PRIVATE_KEY.exists():
        LOCAL_DIR.mkdir(exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        PRIVATE_KEY.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        PUBLIC_KEY.write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
        print(f"Llaves locales creadas en {LOCAL_DIR}", file=sys.stderr)
    return PRIVATE_KEY.read_bytes()


def main() -> int:
    load_dotenv(BASE_DIR / ".env", override=False)
    if (os.environ.get("APP_ENV") or "production").lower() != "local":
        print("Solo disponible con APP_ENV=local.", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser()
    parser.add_argument("--sub", default=str(uuid.uuid4()))
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    pool = os.environ.get("COGNITO_USER_POOL_ID", "us-east-1_localPool")
    issuer = os.environ.get("COGNITO_ISSUER") or f"https://cognito-idp.{region}.amazonaws.com/{pool}"
    now = int(time.time())
    claims = {
        "sub": args.sub,
        "iss": issuer,
        "client_id": os.environ.get("COGNITO_APP_CLIENT_ID", "local-client-id"),
        "token_use": "access",
        "scope": "aws.cognito.signin.user.admin",
        "username": args.sub,
        "iat": now,
        "exp": now + args.minutes * 60,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(claims, ensure_keys(), algorithm="RS256", headers={"kid": "local-dev"})
    print(f"AUTH_LOCAL_PUBLIC_KEY_FILE={PUBLIC_KEY.relative_to(BASE_DIR).as_posix()}", file=sys.stderr)
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
