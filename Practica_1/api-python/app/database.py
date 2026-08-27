"""Pool de conexiones PostgreSQL.

Usa `sslmode`/`sslrootcert` nativos de libpq (vía psycopg2) para hablar
con RDS en verify-full, en vez de construir manualmente el contexto TLS
como hace Node.js en database.service.ts.

`ThreadedConnectionPool` no valida ni descarta conexiones muertas por su
cuenta: si Postgres se reinicia (o RDS hace failover), las conexiones ya
abiertas quedan rotas y psycopg2 lanza `InterfaceError: connection already
closed` en el primer uso posterior, sin que el pool se entere. Por eso
`get_connection()` valida cada conexión con un `SELECT 1` barato antes de
entregarla (equivalente a `pool_pre_ping` de SQLAlchemy) y descarta
cualquiera que falle, en vez de repartirla a quien la pida.
"""

from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from app.config import get_settings

_pool: pg_pool.ThreadedConnectionPool | None = None
_connect_kwargs: dict | None = None

# Cuántas conexiones del pool se prueban antes de rendirse y abrir una nueva
# por fuera del pool. Con varias conexiones abiertas en paralelo, un reinicio
# de Postgres puede dejar más de una muerta a la vez; el respaldo final
# (conexión nueva directa) garantiza corrección sin importar cuántas lo estén.
_INTENTOS_VALIDACION = 5


def _build_connect_kwargs() -> dict:
    settings = get_settings()
    connect_kwargs: dict = {
        "host": settings.bd_host,
        "port": settings.bd_puerto,
        "dbname": settings.bd_nombre,
        "user": settings.bd_usuario,
        "password": settings.bd_contrasena,
        "sslmode": settings.bd_ssl_modo,
    }
    if settings.bd_certificado_ca and settings.bd_ssl_modo in ("verify-ca", "verify-full"):
        connect_kwargs["sslrootcert"] = settings.bd_certificado_ca
    return connect_kwargs


def init_pool() -> None:
    global _pool, _connect_kwargs
    if _pool is not None:
        return

    _connect_kwargs = _build_connect_kwargs()
    _pool = pg_pool.ThreadedConnectionPool(1, 10, **_connect_kwargs)


def close_pool() -> None:
    global _pool, _connect_kwargs
    if _pool is not None:
        _pool.closeall()
        _pool = None
        _connect_kwargs = None


def _esta_viva(conn) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()  # descarta la transacción implícita del SELECT 1
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _obtener_conexion_sana():
    assert _pool is not None
    for _ in range(_INTENTOS_VALIDACION):
        conn = _pool.getconn()
        if _esta_viva(conn):
            return conn
        # Conexión muerta (p. ej. Postgres se reinició): se descarta del pool
        # en vez de devolverla, para que no se le siga repartiendo a nadie más.
        _pool.putconn(conn, close=True)

    # Todas las conexiones probadas del pool estaban muertas: se abre una
    # nueva directamente para no fallar la petición actual. Puede tardar un
    # poco más que lo normal (una reconexión real), lo cual es aceptable.
    assert _connect_kwargs is not None
    return psycopg2.connect(**_connect_kwargs)


def _devolver_conexion(conn) -> None:
    assert _pool is not None
    try:
        _pool.putconn(conn)
    except pg_pool.PoolError:
        # Se abrió por fuera del pool (respaldo tras agotar _INTENTOS_VALIDACION);
        # el pool no la reconoce como propia, así que simplemente se cierra.
        conn.close()


@contextmanager
def get_connection():
    if _pool is None:
        init_pool()
    conn = _obtener_conexion_sana()
    try:
        yield conn
    finally:
        _devolver_conexion(conn)


@contextmanager
def get_cursor(commit: bool = False):
    """Cursor con filas tipo diccionario (equivalente a las filas de `pg` en Node.js)."""
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
