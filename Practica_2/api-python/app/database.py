"""Pool de conexiones PostgreSQL (psycopg 3 + psycopg_pool).

- `check=ConnectionPool.check_connection` valida cada conexión antes de
  entregarla, de modo que una conexión rota por un reinicio o failover de RDS
  se descarta en lugar de fallar la petición.
- El pool se abre sin esperar (`wait=False`): la API arranca aunque la base no
  esté disponible y /health lo reporta con 503.
- `DB_SSLMODE` y `DB_SSLROOTCERT` se pasan tal cual a libpq; en RDS se usa
  `verify-full` con el bundle de certificados de AWS.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import Configuracion, obtener_config

logger = logging.getLogger(__name__)

POOL_MIN = 1
POOL_MAX = 10
CONNECT_TIMEOUT_SEGUNDOS = 5
APPLICATION_NAME = "taskflow-api-python"

_pool: ConnectionPool | None = None


def construir_conninfo(config: Configuracion) -> str:
    parametros = {
        "host": config.db_host,
        "port": config.db_port,
        "dbname": config.db_name,
        "user": config.db_user,
        "password": config.db_password,
        "sslmode": config.db_sslmode,
        "connect_timeout": CONNECT_TIMEOUT_SEGUNDOS,
        "application_name": APPLICATION_NAME,
    }
    if config.db_sslrootcert:
        parametros["sslrootcert"] = config.db_sslrootcert
    return make_conninfo(**parametros)


def abrir_pool() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = ConnectionPool(
        construir_conninfo(obtener_config()),
        min_size=POOL_MIN,
        max_size=POOL_MAX,
        kwargs={"row_factory": dict_row},
        check=ConnectionPool.check_connection,
        open=False,
        name="taskflow",
    )
    _pool.open(wait=False)


def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conexion(timeout: float | None = None) -> Iterator[psycopg.Connection]:
    """Entrega una conexión del pool dentro de una transacción.

    Al salir sin excepción se hace commit; si hay excepción, rollback.
    """
    if _pool is None:
        raise RuntimeError("El pool de base de datos no está abierto.")
    with _pool.connection(timeout=timeout) as conn:
        yield conn


def verificar_conexion(timeout: float) -> bool:
    try:
        with conexion(timeout=timeout) as conn:
            conn.execute(f"SET LOCAL statement_timeout = {int(timeout * 1000)}")
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        logger.warning("La verificación de la base de datos falló.", exc_info=True)
        return False
