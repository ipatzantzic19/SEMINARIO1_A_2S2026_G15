"""Arranque y validación de variables de entorno."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import ConfigError, Settings

BASE_DIR = Path(__file__).resolve().parent.parent

PRODUCTION_ENV = {
    "APP_ENV": "production",
    "AWS_REGION": "us-east-1",
    "COGNITO_USER_POOL_ID": "us-east-1_4UrrCPt8Z",
    "COGNITO_APP_CLIENT_ID": "1feavcj8qvobr4ltshlgnolg5f",
    "RDS_HOST": "db.example.internal",
    "RDS_USER": "semisocial_app",
    "RDS_PASSWORD": "Sup3r-Secret-Value!",
    "RDS_SSLMODE": "verify-full",
    "S3_IMAGES_BUCKET": "semisocial-g15-images-581117996165",
}


def test_production_with_all_variables_loads() -> None:
    settings = Settings.from_env(PRODUCTION_ENV)
    assert settings.is_production
    assert settings.port == 3000
    assert settings.host == "0.0.0.0"
    assert settings.api_base_path == "/api/v1"
    assert settings.cognito.issuer == "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z"
    assert settings.cognito.jwks_uri.endswith("/us-east-1_4UrrCPt8Z/.well-known/jwks.json")
    assert not settings.docs_enabled
    assert "Sup3r-Secret-Value!" not in repr(settings)


def test_missing_app_env_behaves_as_production() -> None:
    with pytest.raises(ConfigError) as info:
        Settings.from_env({})
    message = str(info.value)
    assert "APP_ENV=production" in message
    for name in ("COGNITO_USER_POOL_ID", "COGNITO_APP_CLIENT_ID", "RDS_HOST", "RDS_PASSWORD", "S3_IMAGES_BUCKET"):
        assert name in message


@pytest.mark.parametrize("missing", ["COGNITO_USER_POOL_ID", "COGNITO_APP_CLIENT_ID", "RDS_HOST", "RDS_USER", "RDS_PASSWORD", "S3_IMAGES_BUCKET", "AWS_REGION"])
def test_missing_critical_variable_fails_without_leaking_values(missing: str) -> None:
    env = {k: v for k, v in PRODUCTION_ENV.items() if k != missing}
    with pytest.raises(ConfigError) as info:
        Settings.from_env(env)
    message = str(info.value)
    assert missing in message
    for value in PRODUCTION_ENV.values():
        if value not in ("production", "us-east-1", "verify-full"):
            assert value not in message


def test_database_url_replaces_individual_rds_variables() -> None:
    env = {k: v for k, v in PRODUCTION_ENV.items() if not k.startswith("RDS_")}
    env["DATABASE_URL"] = "postgresql://user:pass@db.example.internal:5432/semisocial"
    settings = Settings.from_env(env)
    assert settings.database.configured
    assert "pass@" not in repr(settings)


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"MOCK_MODE": "true"}, "MOCK_MODE"),
        ({"RDS_SSLMODE": "disable"}, "RDS_SSLMODE"),
        ({"LOG_LEVEL": "DEBUG"}, "LOG_LEVEL"),
        ({"AUTH_LOCAL_PUBLIC_KEY_FILE": "key.pem"}, "AUTH_LOCAL_PUBLIC_KEY_FILE"),
        ({"COGNITO_ISSUER": "https://evil.example.com"}, "COGNITO_ISSUER"),
        ({"CORS_ALLOWED_ORIGINS": "*"}, "CORS_ALLOWED_ORIGINS"),
        ({"PORT": "abc"}, "PORT"),
    ],
)
def test_production_rejects_insecure_settings(overrides: dict[str, str], fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        Settings.from_env({**PRODUCTION_ENV, **overrides})


def test_invalid_app_env_is_rejected() -> None:
    with pytest.raises(ConfigError, match="APP_ENV"):
        Settings.from_env({"APP_ENV": "staging"})


def test_local_allows_defaults_and_mock_mode() -> None:
    settings = Settings.from_env({"APP_ENV": "local", "MOCK_MODE": "true"})
    assert settings.mock_mode
    assert settings.host == "127.0.0.1"
    assert settings.docs_enabled
    assert not settings.database.configured


def _run_entrypoint(env: dict[str, str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    base = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH", "TEMP", "TMP") if k in os.environ}
    base["PYTHONPATH"] = str(BASE_DIR)
    base["PYTHONIOENCODING"] = "utf-8"
    base["ENV_FILE"] = str(tmp_path / "missing.env")  # aísla de un .env local
    return subprocess.run(
        [sys.executable, "-m", "app"],
        env={**base, **env},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_entrypoint_exits_with_clear_message_when_critical_env_missing(tmp_path: Path) -> None:
    env = {k: v for k, v in PRODUCTION_ENV.items() if k != "RDS_HOST"}
    result = _run_entrypoint(env, tmp_path)
    assert result.returncode == 2
    assert "[CONFIG ERROR]" in result.stderr
    assert "RDS_HOST" in result.stderr
    assert "Sup3r-Secret-Value!" not in result.stderr + result.stdout


def test_entrypoint_without_any_env_fails_closed(tmp_path: Path) -> None:
    result = _run_entrypoint({}, tmp_path)
    assert result.returncode == 2
    assert "APP_ENV=production" in result.stderr
