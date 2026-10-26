"""/ws/chat sobre un uvicorn REAL (PRO-16): paquete ``websockets``, códigos de cierre,
límite de frame, 503 previo al upgrade y, sobre todo, que ningún log imprima la
query string (el token va en la URL). El TestClient no pasa por uvicorn, así que
estas pruebas son las únicas que ven la línea ``"WebSocket /ws/chat?token=…" [accepted]``.
"""

from __future__ import annotations

import io
import json
import logging
import threading
from contextlib import contextmanager

import pytest
import uvicorn
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

from app.common.logs import build_handler, setup_logging
from app.modules.chat.websocket import MAX_FRAME_BYTES
from tests.chat_world import A_ID, A_SUB, B_ID, B_SUB, C_ID, make_world, send_frame, wait_ready, wait_until, ws_url
from tests.conftest import FakeDatabase


@contextmanager
def serve(app):
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_config=None,  # igual que app/__main__.py
        access_log=False,
        ws_max_size=MAX_FRAME_BYTES,
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_until(lambda: server.started, timeout=10)
    try:
        yield server.servers[0].sockets[0].getsockname()[1]
    finally:
        server.should_exit = True
        thread.join(15)


def url(port: int, token: str | None, friend: str | None) -> str:
    return f"ws://127.0.0.1:{port}{ws_url(token, friend)}"


@pytest.fixture
def raw_and_safe_logs():
    """Dos destinos sobre el logger raíz: uno SIN filtro (prueba que el riesgo existe) y
    el de producción (build_handler, con RedactionFilter)."""
    raw, safe = io.StringIO(), io.StringIO()
    raw_handler = logging.StreamHandler(raw)
    safe_handler = build_handler(safe)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(raw_handler)
    root.addHandler(safe_handler)
    root.setLevel(logging.INFO)
    try:
        yield raw, safe
    finally:
        root.removeHandler(raw_handler)
        root.removeHandler(safe_handler)
        root.setLevel(previous)


def test_uvicorn_never_logs_token_friend_or_content(build_app, make_token, raw_and_safe_logs) -> None:
    raw, safe = raw_and_safe_logs
    world = make_world(build_app)
    app = world.apps[0]
    token = make_token(A_SUB)
    secret = "contenido-secreto-77c1"
    with serve(app) as port:
        wait_ready(app)
        with connect(url(port, token, B_ID)) as ws:
            assert json.loads(ws.recv())["event"] == "connected"
            ws.send(json.dumps(send_frame(B_ID, secret)))
            assert json.loads(ws.recv())["event"] == "message:ack"
        with pytest.raises(ConnectionClosed):  # rechazo (no son amigos): uvicorn también lo registra
            with connect(url(port, token, C_ID)) as ws:
                ws.recv()
        with pytest.raises(ConnectionClosed):  # sin token
            with connect(url(port, None, B_ID)) as ws:
                ws.recv()

    # Sensibilidad de la prueba: uvicorn SÍ escribe la URL completa en uvicorn.error...
    assert "WebSocket /ws/chat?token=" in raw.getvalue()
    # ...y la configuración de producción la deja sin query string.
    logs = safe.getvalue()
    assert "WebSocket /ws/chat" in logs and "[accepted]" in logs
    for forbidden in (token, token.split(".")[1], "token=", "friendId", B_ID, secret):
        assert forbidden not in logs, forbidden
    assert A_ID not in logs  # ni el userId


def test_setup_logging_silences_websockets_debug_and_uvicorn_access() -> None:
    setup_logging("DEBUG")
    try:
        assert logging.getLogger("websockets").level == logging.WARNING
        assert logging.getLogger("uvicorn.access").disabled
    finally:
        logging.getLogger().handlers.clear()
        setup_logging("INFO")


def test_close_codes_reach_the_client_through_uvicorn(build_app, make_token) -> None:
    world = make_world(build_app)
    with serve(world.apps[0]) as port:
        wait_ready(world.apps[0])
        expectations = [
            (url(port, None, B_ID), 4401, "Unauthorized: token is required"),
            (url(port, make_token(A_SUB), None), 4400, "Bad Request: friendId is required"),
            (url(port, make_token(A_SUB, exp=1), B_ID), 4401, "Unauthorized: invalid token"),
            (url(port, make_token(A_SUB), C_ID), 4403, "Forbidden: NOT_FRIENDS"),
        ]
        for target, code, reason in expectations:
            with pytest.raises(ConnectionClosed) as closed:
                with connect(target) as ws:
                    ws.recv()
            # El upgrade se acepta y luego se cierra con el código: el frontend lo distingue de 1006.
            assert (closed.value.rcvd.code, closed.value.rcvd.reason) == (code, reason)


def test_oversized_frame_is_closed_with_1009_by_uvicorn(build_app, make_token) -> None:
    world = make_world(build_app)
    with serve(world.apps[0]) as port:
        wait_ready(world.apps[0])
        with connect(url(port, make_token(A_SUB), B_ID)) as ws:
            ws.recv()
            ws.send("x" * (MAX_FRAME_BYTES + 1))
            with pytest.raises(ConnectionClosed) as closed:
                ws.recv()
    assert closed.value.rcvd.code == 1009


def test_without_database_the_upgrade_is_rejected_with_http_503(build_app, make_token) -> None:
    app = build_app(database=FakeDatabase(configured=False))
    with serve(app) as port:
        with pytest.raises(InvalidStatus) as rejected:
            with connect(url(port, make_token(A_SUB), B_ID)):
                pass
    response = rejected.value.response
    assert response.status_code == 503
    assert json.loads(response.body)["code"] == "SERVICE_UNAVAILABLE"


def test_two_uvicorn_instances_broadcast_through_the_shared_bus(build_app, make_token) -> None:
    world = make_world(build_app, instances=2)
    app1, app2 = world.apps
    with serve(app1) as port1, serve(app2) as port2:
        wait_ready(app1), wait_ready(app2)
        with connect(url(port1, make_token(A_SUB), B_ID)) as a, connect(url(port2, make_token(B_SUB), A_ID)) as b:
            a.recv(), b.recv()
            a.send(json.dumps(send_frame(B_ID, "A → B entre instancias")))
            assert json.loads(a.recv())["event"] == "message:ack"
            assert json.loads(b.recv())["data"]["body"] == "A → B entre instancias"
            b.send(json.dumps(send_frame(A_ID, "B → A entre instancias", "d4a3b2a1-0000-4000-8000-111122223333")))
            assert json.loads(b.recv())["event"] == "message:ack"
            assert json.loads(a.recv())["data"]["body"] == "B → A entre instancias"


def test_chat_smoke_script_logic_against_two_real_servers(build_app, make_token, capsys) -> None:
    """scripts/chat_smoke.py (sin login): mismos pasos que contra Node, pero con dos uvicorn Python."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "chat_smoke", Path(__file__).resolve().parents[1] / "scripts" / "chat_smoke.py"
    )
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)

    world = make_world(build_app, instances=2)
    app1, app2 = world.apps
    with serve(app1) as port1, serve(app2) as port2:
        wait_ready(app1), wait_ready(app2)
        base1, base2 = f"http://127.0.0.1:{port1}", f"http://127.0.0.1:{port2}"
        ws_a, reason = smoke.open_socket(base1, make_token(A_SUB), B_ID)
        assert ws_a is not None, reason
        ws_b, reason = smoke.open_socket(base2, make_token(B_SUB), A_ID)
        assert ws_b is not None, reason
        try:
            assert smoke.exchange("A→B", ws_a, ws_b, B_ID) is True
            assert smoke.exchange("B→A", ws_b, ws_a, A_ID) is True
        finally:
            ws_a.close(), ws_b.close()
        _, reason = smoke.open_socket(base1, make_token(A_SUB), C_ID)

    output = capsys.readouterr().out
    assert reason == "cerrado por el servidor (código 4403)"
    assert output.count("OK   ") == 4 and "FALLO" not in output
    assert "ms)" in output  # latencia por paso
    assert "token" not in output.lower() and "smoke-" not in output  # ni tokens ni texto de mensajes
