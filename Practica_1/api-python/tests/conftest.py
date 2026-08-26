"""Fixtures compartidas de pytest.

Requiere `docker compose up -d` (ver ../docker-compose.yml) antes de correr
la suite: los tests usan el Postgres local real, no un mock de base de datos.

Las variables de entorno se fijan aquí ANTES de importar `app.main`, porque
`create_app()` valida la configuración obligatoria (incluida SECRETO_JWT) al
arrancar. Con `setdefault` no se pisa nada que el desarrollador ya tenga
exportado en su propio shell.
"""

import os

os.environ.setdefault("BD_HOST", "localhost")
os.environ.setdefault("BD_PUERTO", "5433")
os.environ.setdefault("BD_NOMBRE", "cloudcinema")
os.environ.setdefault("BD_USUARIO", "cloudcinema_dev")
os.environ.setdefault("BD_CONTRASENA", "cloudcinema_dev")
os.environ.setdefault("BD_SSL_MODO", "disable")
os.environ.setdefault("BD_CERTIFICADO_CA", "")
os.environ.setdefault("REGION_AWS", "us-east-1")
os.environ.setdefault("BUCKET_IMAGENES", "practica1-images-g15-test")
os.environ.setdefault("SECRETO_JWT", "secreto-de-pruebas-no-usar-en-produccion")
os.environ.setdefault("PORT", "8000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import get_cursor  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def limpiar_usuarios():
    """Aísla cada test: usuarios (y lista_reproduccion, por CASCADE) se vacían antes de cada uno.
    peliculas (datos semilla) no se toca."""
    with get_cursor(commit=True) as cur:
        cur.execute("TRUNCATE TABLE usuarios RESTART IDENTITY CASCADE;")
    yield
