"""Configuración común de pruebas.

Las variables apuntan por defecto al PostgreSQL de desarrollo de
docker-compose.yml. Se pueden sobrescribir con variables de entorno reales.
"""

import os

VALORES_PRUEBA = {
    "DB_HOST": "localhost",
    "DB_PORT": "5433",
    "DB_NAME": "taskflow",
    "DB_USER": "taskflow_dev",
    "DB_PASSWORD": "taskflow_dev",
    "DB_SSLMODE": "disable",
    "DB_SSLROOTCERT": "",
    "JWT_SECRET": "secreto-solo-para-pruebas-con-32-bytes-o-mas",
    "JWT_EXPIRES_IN": "3600",
    "CORS_ORIGINS": "",
}
for nombre, valor in VALORES_PRUEBA.items():
    os.environ.setdefault(nombre, valor)

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import obtener_config  # noqa: E402
from app.database import construir_conninfo  # noqa: E402


@pytest.fixture
def cliente():
    """Cliente SIN ciclo de vida: no abre el pool. Para pruebas que no tocan la base."""
    from app.main import app

    return TestClient(app)


@pytest.fixture
def cliente_bd(bd_limpia):
    """Cliente con ciclo de vida completo (abre el pool) sobre una base limpia; se omite sin PostgreSQL."""
    from app.main import app

    with TestClient(app) as cliente_prueba:
        yield cliente_prueba


@pytest.fixture(scope="session")
def _error_conexion_bd() -> str | None:
    """Se comprueba una sola vez por sesión si el PostgreSQL de desarrollo responde."""
    try:
        psycopg.connect(construir_conninfo(obtener_config()), connect_timeout=2).close()
    except psycopg.OperationalError as exc:
        return str(exc).splitlines()[-1]
    return None


@pytest.fixture
def bd_limpia(_error_conexion_bd):
    """Deja las tablas vacías; omite la prueba si el PostgreSQL de desarrollo no responde."""
    if _error_conexion_bd:
        pytest.skip(f"PostgreSQL de desarrollo no disponible (docker compose up -d): {_error_conexion_bd}")
    conn = psycopg.connect(construir_conninfo(obtener_config()))
    with conn:
        conn.execute("TRUNCATE usuarios, tareas, archivos RESTART IDENTITY CASCADE")
    conn.close()
    yield
