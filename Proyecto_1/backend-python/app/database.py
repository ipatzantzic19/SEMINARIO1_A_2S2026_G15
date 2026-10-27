"""Pool de conexiones PostgreSQL (RDS).

Se usa el pool SÍNCRONO de psycopg y las consultas se ejecutan en el
threadpool de Starlette. Motivo: el modo asíncrono de psycopg no funciona con
el ``ProactorEventLoop`` por defecto de Windows; el pool síncrono funciona
igual en Windows (desarrollo) y Linux (EC2) sin fijar políticas de event loop.

El esquema lo define ``Proyecto_1/database/migrations``; esta API no crea
tablas ni ejecuta migraciones.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Protocol

from psycopg import Connection
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from app.config import DatabaseSettings

logger = logging.getLogger("semisocial.database")

EXPECTED_MIGRATIONS = ("000_bootstrap", "001_core_schema", "002_indexes")


class DatabaseUnavailable(RuntimeError):
    """No fue posible conectar con PostgreSQL."""


class DatabaseProtocol(Protocol):
    @property
    def configured(self) -> bool: ...

    def open(self, *, required: bool) -> None: ...

    def close(self) -> None: ...

    def ping(self) -> bool: ...


class Database:
    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._pool: ConnectionPool | None = None

    @property
    def configured(self) -> bool:
        return self._settings.configured

    def _conninfo(self) -> str:
        s = self._settings
        extra = {
            "sslmode": s.sslmode,
            "connect_timeout": s.connect_timeout,
            "application_name": "semisocial-python",
        }
        if s.sslrootcert:
            extra["sslrootcert"] = s.sslrootcert
        if s.database_url:
            return make_conninfo(s.database_url, **extra)
        return make_conninfo(
            host=s.host, port=s.port, dbname=s.name, user=s.user, password=s.password, **extra
        )

    def open(self, *, required: bool) -> None:
        """Abre el pool y comprueba la conexión.

        ``required=True`` (producción): si no conecta, lanza ``DatabaseUnavailable``
        y el arranque falla. ``required=False`` (local): solo advierte y el pool
        sigue reintentando en segundo plano.
        """
        if not self.configured:
            if required:
                raise DatabaseUnavailable("PostgreSQL no está configurado.")
            logger.warning("PostgreSQL no configurado (APP_ENV=local); /health no lo comprobará.")
            return

        s = self._settings
        self._pool = ConnectionPool(
            conninfo=self._conninfo(),
            min_size=s.pool_min_size,
            max_size=s.pool_max_size,
            timeout=s.connect_timeout,
            open=False,
            name="semisocial-python",
        )
        target = f"{s.host or 'DATABASE_URL'}:{s.port}/{s.name}"
        try:
            self._pool.open(wait=True, timeout=s.connect_timeout)
            self._check_migrations()
            logger.info("Conexión a PostgreSQL verificada (%s, sslmode=%s).", target, s.sslmode)
        except Exception as exc:  # noqa: BLE001
            # No se incluye el mensaje de psycopg: puede contener datos de conexión.
            if required:
                self._pool.close()
                self._pool = None
                raise DatabaseUnavailable(
                    f"No fue posible conectar a PostgreSQL ({target}): {type(exc).__name__}."
                ) from None
            logger.warning(
                "No fue posible conectar a PostgreSQL (%s): %s. Se reintentará en segundo plano.",
                target,
                type(exc).__name__,
            )

    def _check_migrations(self) -> None:
        with self.connection() as conn:
            exists = conn.execute("SELECT to_regclass('public.schema_migrations') IS NOT NULL").fetchone()
            if not exists or not exists[0]:
                logger.warning("No existe schema_migrations; aplique Proyecto_1/database/migrations.")
                return
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        pending = [m for m in EXPECTED_MIGRATIONS if m not in applied]
        if pending:
            logger.warning("Migraciones pendientes en RDS: %s", ", ".join(pending))

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        if self._pool is None:
            raise DatabaseUnavailable("Pool de PostgreSQL no disponible.")
        with self._pool.connection(timeout=self._settings.connect_timeout) as conn:
            yield conn

    def connect_dedicated(self, application_name: str) -> Connection:
        """Conexión propia en autocommit, FUERA del pool (LISTEN/NOTIFY de PRO-16).

        Mismos parámetros y TLS que el pool, más keepalives de TCP para detectar
        una conexión muerta (el listener reconecta). El llamante la cierra.
        """
        if not self.configured:
            raise DatabaseUnavailable("PostgreSQL no está configurado.")
        conninfo = make_conninfo(
            self._conninfo(),
            application_name=application_name,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )
        return Connection.connect(conninfo, autocommit=True)

    def ping(self) -> bool:
        if self._pool is None:
            return False
        try:
            with self._pool.connection(timeout=2) as conn:
                row = conn.execute("SELECT 1").fetchone()
            return bool(row and row[0] == 1)
        except Exception:  # noqa: BLE001
            return False
