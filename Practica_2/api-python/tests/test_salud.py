import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import obtener_config

SALUD_OK = {
    "exito": True,
    "datos": {"estado": "ok", "servicio": "taskflow-api", "implementacion": "python"},
}


def test_health_200_cuando_la_bd_responde(cliente, monkeypatch):
    monkeypatch.setattr(database, "verificar_conexion", lambda timeout: True)

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == SALUD_OK


def test_health_503_cuando_la_bd_no_responde(monkeypatch):
    # Puerto cerrado: no hay PostgreSQL escuchando, se agota el tiempo de /health.
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "1")
    obtener_config.cache_clear()
    try:
        from app.main import crear_app

        with TestClient(crear_app()) as cliente_sin_bd:
            respuesta = cliente_sin_bd.get("/health")
    finally:
        obtener_config.cache_clear()

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "exito": False,
        "error": {"codigo": "BD_NO_DISPONIBLE", "mensaje": "La base de datos no está disponible."},
    }


@pytest.mark.integracion
def test_health_200_con_postgresql_real(cliente_bd):
    respuesta = cliente_bd.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == SALUD_OK
