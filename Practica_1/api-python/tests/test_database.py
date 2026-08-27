"""Resiliencia del pool ante conexiones muertas.

No hace falta apagar el contenedor de Docker para reproducir el escenario:
cerrar una conexión directamente (`conn.close()`) y devolverla al pool tal
cual dejan al pool exactamente en el mismo estado que un reinicio real de
Postgres — la conexión queda "muerta" pero el pool no lo sabe, y el primer
`cursor()`/`execute()` sobre ella lanza la misma `psycopg2.InterfaceError:
connection already closed` que se observó reiniciando cloudcinema-postgres-dev
de verdad durante la verificación manual de PRA-12.
"""

import app.database as database


def _matar_una_conexion_del_pool():
    """Saca una conexión del pool, la cierra, y la devuelve como si el pool
    no supiera que está muerta — así es exactamente como queda una conexión
    pooled cuando Postgres se reinicia por debajo."""
    conn_muerta = database._pool.getconn()
    conn_muerta.close()
    database._pool.putconn(conn_muerta)


def test_get_connection_descarta_conexion_muerta_y_entrega_una_sana():
    database.init_pool()
    _matar_una_conexion_del_pool()

    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)


def test_get_cursor_funciona_despues_de_una_conexion_muerta_en_el_pool():
    database.init_pool()
    _matar_una_conexion_del_pool()

    with database.get_cursor() as cur:
        cur.execute("SELECT 1 AS uno")
        assert cur.fetchone()["uno"] == 1


def test_todas_las_conexiones_del_pool_muertas_no_rompe_la_peticion():
    """Simula que TODAS las conexiones que el pool alcanzó a abrir están
    muertas a la vez (peor caso tras un reinicio bajo carga concurrente):
    debe caer en el respaldo de abrir una conexión nueva por fuera del pool."""
    database.init_pool()

    # Fuerza al pool a tener varias conexiones abiertas y libres.
    conexiones = [database._pool.getconn() for _ in range(3)]
    for conn in conexiones:
        database._pool.putconn(conn)

    # Mata TODO lo que esté libre en el pool en este momento, sin importar
    # cuántas sean ni qué haya quedado de otros tests (evita depender del
    # orden de ejecución de la suite).
    for conn in database._pool._pool:
        conn.close()

    with database.get_cursor() as cur:
        cur.execute("SELECT 1 AS uno")
        assert cur.fetchone()["uno"] == 1
