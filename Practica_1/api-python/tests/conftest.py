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

import boto3  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402

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


@pytest.fixture(autouse=True)
def s3_mock():
    """Intercepta boto3 con moto — no requiere ninguna credencial real de AWS ni
    usuario IAM personal, tal como decidió el equipo (ver
    docs/infrastructure.md). El código de app/s3_service.py no
    sabe que moto existe: crea el cliente boto3 normal, moto lo intercepta a
    nivel de botocore mientras este bloque `with` está activo."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=os.environ["REGION_AWS"])
        s3.create_bucket(Bucket=os.environ["BUCKET_IMAGENES"])
        yield


def archivo_imagen_de_prueba(nombre: str = "foto.png", content_type: str = "image/png") -> dict:
    contenido = b"contenido-binario-de-prueba-no-es-una-imagen-real"
    return {"fotoPerfil": (nombre, contenido, content_type)}
