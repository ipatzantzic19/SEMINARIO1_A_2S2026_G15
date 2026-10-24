"""Carga y validación de variables de entorno.

La validación es manual (no pydantic-settings) para controlar el mensaje de
error: solo se mencionan NOMBRES de variables, nunca sus valores.

Reglas:
- ``APP_ENV`` ausente se interpreta como ``production`` (fail closed).
- En ``production`` se exigen Cognito, RDS y S3 reales y se prohíbe ``MOCK_MODE``.
- En ``local`` se permiten valores por defecto y mocks explícitos.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

APP_VERSION = "1.0.0"  # Versión del contrato común (openapi.yaml info.version).
SERVICE_NAME = "python"

VALID_ENVS = ("local", "production")
SECURE_SSL_MODES = ("require", "verify-ca", "verify-full")
VALID_SSL_MODES = ("disable", "allow", "prefer", *SECURE_SSL_MODES)

_POOL_ID_RE = re.compile(r"^[a-z]{2}-[a-z]+-\d_[A-Za-z0-9]+$")
_REGION_RE = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")
_LEX_ID_RE = re.compile(r"^[0-9A-Za-z]{10}$")
_LEX_LOCALE_RE = re.compile(r"^[a-z]{2}_[0-9A-Z]{2,3}$")
LEX_TEST_ALIAS_ID = "TSTALIASID"  # Alias de prueba de Lex: apunta al borrador.


class ConfigError(RuntimeError):
    """Configuración inválida. El mensaje nunca contiene valores de variables."""


@dataclass(frozen=True)
class CognitoSettings:
    region: str
    user_pool_id: str
    app_client_id: str
    issuer: str
    jwks_uri: str
    # Solo local: llave pública PEM para validar tokens emitidos localmente.
    local_public_key_file: Path | None = None
    # Timeout de conexión y lectura hacia la API de Cognito (PRO-14).
    timeout_seconds: int = 5


@dataclass(frozen=True)
class DatabaseSettings:
    database_url: str | None = field(default=None, repr=False)
    host: str | None = None
    port: int = 5432
    name: str = "semisocial"
    user: str | None = None
    password: str | None = field(default=None, repr=False)
    sslmode: str = "verify-full"
    sslrootcert: str | None = None
    pool_min_size: int = 1
    pool_max_size: int = 10
    connect_timeout: int = 5

    @property
    def configured(self) -> bool:
        return bool(self.database_url or self.host)


@dataclass(frozen=True)
class S3Settings:
    images_bucket: str
    profile_prefix: str
    face_reference_prefix: str
    face_capture_prefix: str
    posts_prefix: str
    # Región del bucket (URL pública) y timeout de HeadObject (PRO-14).
    region: str = "us-east-1"
    timeout_seconds: int = 5


@dataclass(frozen=True)
class TranslateSettings:
    region: str
    timeout_seconds: int = 5


@dataclass(frozen=True)
class RekognitionSettings:
    region: str
    timeout_seconds: int = 5


@dataclass(frozen=True)
class LexSettings:
    region: str
    bot_id: str | None = None
    bot_alias_id: str | None = None
    locale_id: str = "es_419"
    timeout_seconds: int = 5

    @property
    def configured(self) -> bool:
        return bool(self.bot_id and self.bot_alias_id)


@dataclass(frozen=True)
class Settings:
    app_env: str
    mock_mode: bool
    host: str
    port: int
    api_base_path: str
    log_level: str
    cors_allowed_origins: tuple[str, ...]
    cognito: CognitoSettings
    database: DatabaseSettings
    s3: S3Settings
    translate: TranslateSettings
    lex: LexSettings
    rekognition: RekognitionSettings = RekognitionSettings(region="us-east-1")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.app_env == "local"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        return load_settings(os.environ if environ is None else environ)


def _get(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_bool(env: Mapping[str, str], name: str, errors: list[str]) -> bool:
    raw = _get(env, name)
    if raw is None:
        return False
    if raw.lower() in ("true", "1", "yes"):
        return True
    if raw.lower() in ("false", "0", "no"):
        return False
    errors.append(f"{name} debe ser true o false")
    return False


def _parse_int(
    env: Mapping[str, str], name: str, default: int, errors: list[str], *, minimum: int = 1, maximum: int = 65535
) -> int:
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"{name} debe ser un entero")
        return default
    if not minimum <= value <= maximum:
        errors.append(f"{name} fuera de rango ({minimum}-{maximum})")
    return value


def load_settings(env: Mapping[str, str]) -> Settings:
    errors: list[str] = []
    missing: list[str] = []

    app_env = (_get(env, "APP_ENV") or "production").lower()
    if app_env not in VALID_ENVS:
        raise ConfigError(f"APP_ENV inválida; valores permitidos: {', '.join(VALID_ENVS)}")
    production = app_env == "production"

    mock_mode = _parse_bool(env, "MOCK_MODE", errors)
    if production and mock_mode:
        errors.append("MOCK_MODE=true no está permitido con APP_ENV=production")

    def require(name: str, local_default: str | None = None) -> str | None:
        value = _get(env, name)
        if value is None:
            if production:
                missing.append(name)
                return None
            return local_default
        return value

    port = _parse_int(env, "PORT", 3000, errors)
    host = _get(env, "HOST") or ("0.0.0.0" if production else "127.0.0.1")

    api_base_path = _get(env, "API_BASE_PATH") or "/api/v1"
    if not api_base_path.startswith("/") or api_base_path.endswith("/") or api_base_path == "/":
        errors.append("API_BASE_PATH debe iniciar con '/' y no terminar en '/' (p. ej. /api/v1)")

    log_level = (_get(env, "LOG_LEVEL") or "INFO").upper()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        errors.append("LOG_LEVEL debe ser DEBUG, INFO, WARNING o ERROR")
    if production and log_level == "DEBUG":
        errors.append("LOG_LEVEL=DEBUG no está permitido con APP_ENV=production")

    cors = tuple(o.strip() for o in (_get(env, "CORS_ALLOWED_ORIGINS") or "").split(",") if o.strip())
    if "*" in cors:
        errors.append("CORS_ALLOWED_ORIGINS no admite '*'; liste orígenes explícitos")

    # --- Cognito ---------------------------------------------------------
    region = require("AWS_REGION", "us-east-1") or "us-east-1"
    pool_id = require("COGNITO_USER_POOL_ID", "us-east-1_localPool")
    client_id = require("COGNITO_APP_CLIENT_ID", "local-client-id")
    if pool_id and not _POOL_ID_RE.match(pool_id):
        errors.append("COGNITO_USER_POOL_ID no tiene el formato <region>_<id>")
    issuer = _get(env, "COGNITO_ISSUER")
    jwks_uri = _get(env, "COGNITO_JWKS_URI")
    if pool_id:
        expected_issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
        issuer = issuer or expected_issuer
        jwks_uri = jwks_uri or f"{issuer}/.well-known/jwks.json"
        if production and issuer != expected_issuer:
            errors.append("COGNITO_ISSUER no corresponde a AWS_REGION/COGNITO_USER_POOL_ID")
    cognito_timeout = _parse_int(env, "COGNITO_TIMEOUT_SECONDS", 5, errors, maximum=30)
    local_key_raw = _get(env, "AUTH_LOCAL_PUBLIC_KEY_FILE")
    local_key: Path | None = None
    if local_key_raw:
        if production:
            errors.append("AUTH_LOCAL_PUBLIC_KEY_FILE solo se permite con APP_ENV=local")
        else:
            local_key = Path(local_key_raw)
            if not local_key.is_file():
                errors.append("AUTH_LOCAL_PUBLIC_KEY_FILE no apunta a un archivo existente")

    # --- RDS -------------------------------------------------------------
    database_url = _get(env, "DATABASE_URL")
    rds_host = _get(env, "RDS_HOST")
    rds_user = _get(env, "RDS_USER")
    rds_password = _get(env, "RDS_PASSWORD")
    rds_database = _get(env, "RDS_DATABASE") or "semisocial"
    if production and not database_url:
        for name, value in (("RDS_HOST", rds_host), ("RDS_USER", rds_user), ("RDS_PASSWORD", rds_password)):
            if value is None:
                missing.append(name)
    sslmode = (_get(env, "RDS_SSLMODE") or ("verify-full" if production else "prefer")).lower()
    if sslmode not in VALID_SSL_MODES:
        errors.append(f"RDS_SSLMODE debe ser uno de: {', '.join(VALID_SSL_MODES)}")
    elif production and sslmode not in SECURE_SSL_MODES:
        errors.append(f"RDS_SSLMODE debe ser {', '.join(SECURE_SSL_MODES)} con APP_ENV=production")
    pool_min = _parse_int(env, "DB_POOL_MIN_SIZE", 1, errors, minimum=0, maximum=50)
    pool_max = _parse_int(env, "DB_POOL_MAX_SIZE", 10, errors, minimum=1, maximum=100)
    if pool_min > pool_max:
        errors.append("DB_POOL_MIN_SIZE no puede ser mayor que DB_POOL_MAX_SIZE")

    database = DatabaseSettings(
        database_url=database_url,
        host=rds_host,
        port=_parse_int(env, "RDS_PORT", 5432, errors),
        name=rds_database,
        user=rds_user,
        password=rds_password,
        sslmode=sslmode,
        sslrootcert=_get(env, "RDS_SSLROOTCERT"),
        pool_min_size=pool_min,
        pool_max_size=pool_max,
        connect_timeout=_parse_int(env, "DB_CONNECT_TIMEOUT", 5, errors, maximum=60),
    )

    # --- S3 --------------------------------------------------------------
    s3 = S3Settings(
        images_bucket=require("S3_IMAGES_BUCKET", "semisocial-g15-images-581117996165") or "",
        profile_prefix=_get(env, "S3_PROFILE_PREFIX") or "Fotos_Perfil/public/",
        face_reference_prefix=_get(env, "S3_FACE_REFERENCE_PREFIX") or "Fotos_Perfil/references/",
        face_capture_prefix=_get(env, "S3_FACE_CAPTURE_PREFIX") or "Fotos_Perfil/captures/",
        posts_prefix=_get(env, "S3_POSTS_PREFIX") or "Fotos_Publicadas/",
        region=region,
        timeout_seconds=_parse_int(env, "S3_TIMEOUT_SECONDS", 5, errors, maximum=30),
    )

    # --- Amazon Translate (opcionales; credenciales por la cadena por defecto) ---
    translate_region = _get(env, "TRANSLATE_REGION") or region
    if not _REGION_RE.match(translate_region):
        errors.append("TRANSLATE_REGION no tiene el formato de una región AWS (p. ej. us-east-1)")
    translate = TranslateSettings(
        region=translate_region,
        timeout_seconds=_parse_int(env, "TRANSLATE_TIMEOUT_SECONDS", 5, errors, maximum=30),
    )

    # --- Amazon Lex V2 (opcionales; sin bot configurado /bot/messages responde 503) ---
    lex_region = _get(env, "LEX_REGION") or region
    if not _REGION_RE.match(lex_region):
        errors.append("LEX_REGION no tiene el formato de una región AWS (p. ej. us-east-1)")
    lex_bot_id = _get(env, "LEX_BOT_ID")
    lex_alias_id = _get(env, "LEX_BOT_ALIAS_ID")
    if bool(lex_bot_id) != bool(lex_alias_id):
        errors.append("LEX_BOT_ID y LEX_BOT_ALIAS_ID deben definirse juntas")
    for name, value in (("LEX_BOT_ID", lex_bot_id), ("LEX_BOT_ALIAS_ID", lex_alias_id)):
        if value and not _LEX_ID_RE.match(value):
            errors.append(f"{name} debe tener 10 caracteres alfanuméricos")
    if production and lex_alias_id == LEX_TEST_ALIAS_ID:
        errors.append("LEX_BOT_ALIAS_ID no puede ser el alias de prueba con APP_ENV=production")
    lex_locale = _get(env, "LEX_LOCALE_ID") or "es_419"
    if not _LEX_LOCALE_RE.match(lex_locale):
        errors.append("LEX_LOCALE_ID no tiene el formato de un locale de Lex (p. ej. es_419)")
    lex = LexSettings(
        region=lex_region,
        bot_id=lex_bot_id,
        bot_alias_id=lex_alias_id,
        locale_id=lex_locale,
        timeout_seconds=_parse_int(env, "LEX_TIMEOUT_SECONDS", 5, errors, maximum=30),
    )

    # --- Amazon Rekognition (PRO-34; credenciales por la cadena por defecto) ---
    rekognition_region = _get(env, "REKOGNITION_REGION") or region
    if not _REGION_RE.match(rekognition_region):
        errors.append("REKOGNITION_REGION no tiene el formato de una región AWS (p. ej. us-east-1)")
    rekognition = RekognitionSettings(
        region=rekognition_region,
        timeout_seconds=_parse_int(env, "REKOGNITION_TIMEOUT_SECONDS", 5, errors, maximum=30),
    )

    if missing or errors:
        parts = []
        if missing:
            parts.append("Faltan variables críticas: " + ", ".join(dict.fromkeys(missing)))
        parts.extend(errors)
        raise ConfigError(f"Configuración inválida (APP_ENV={app_env}). " + "; ".join(parts) + ".")

    return Settings(
        app_env=app_env,
        mock_mode=mock_mode,
        host=host,
        port=port,
        api_base_path=api_base_path,
        log_level=log_level,
        cors_allowed_origins=cors,
        cognito=CognitoSettings(
            region=region,
            user_pool_id=pool_id or "",
            app_client_id=client_id or "",
            issuer=issuer or "",
            jwks_uri=jwks_uri or "",
            local_public_key_file=local_key,
            timeout_seconds=cognito_timeout,
        ),
        database=database,
        s3=s3,
        translate=translate,
        lex=lex,
        rekognition=rekognition,
    )
