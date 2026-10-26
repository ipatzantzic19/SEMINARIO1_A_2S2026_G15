"""Prueba MANUAL de interoperabilidad del chat Python <-> Node (PRO-16).

No forma parte de pytest ni de CI. Inicia sesión como A en la API Python local y
como B en el origen público (CloudFront → ALB → Node), conecta A al WebSocket de
Python y B al de Node, y comprueba en los DOS sentidos que el mensaje llega al
otro usuario y que el emisor recibe su ack (difusión LISTEN/NOTIFY por RDS).

Seguridad: las contraseñas se leen con getpass (sin eco, sin argumentos ni
variables de entorno); nunca se imprimen tokens, contraseñas, URLs de socket ni
el texto de los mensajes. Solo se escribe OK o FALLO por paso y la latencia.

Uso (desde backend-python, con el venv activo y la API Python en marcha, con
RDS configurado; ver docs/api/python-chat.md §8):
    python scripts/chat_smoke.py --public-origin https://<dominio>.cloudfront.net \\
        --email-a a@example.com --email-b b@example.com

A y B deben ser amigos con perfil completo. Usa el mismo paquete que la API
(websockets, requirements.txt).
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from urllib import error, request
from urllib.parse import quote, urlsplit

from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.sync.client import ClientConnection, connect

TIMEOUT = 10.0
failures = 0


def report(ok: bool, step: str, detail: str = "", started: float | None = None, until: float | None = None) -> bool:
    """Una línea por paso. La latencia es ``until - started`` (o hasta ahora si falta ``until``)."""
    global failures
    latency = ""
    if started is not None:
        latency = f" ({((until or time.perf_counter()) - started) * 1000:.0f} ms)"
    suffix = f": {detail}" if detail else ""
    print(f"{'OK   ' if ok else 'FALLO'} {step}{latency}{suffix}")
    if not ok:
        failures += 1
    return ok


def http_json(method: str, url: str, token: str | None = None, body: dict | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read() or b"null")
    except error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"null")
        except ValueError:
            return exc.code, None


def login(base: str, email: str, password: str) -> str | None:
    status, body = http_json("POST", f"{base}/api/v1/auth/login", body={"email": email, "password": password})
    if status == 200 and isinstance(body, dict) and body.get("accessToken"):
        return body["accessToken"]
    return None


def user_id(base: str, token: str) -> str | None:
    status, body = http_json("GET", f"{base}/api/v1/me", token)
    return body.get("userId") if status == 200 and isinstance(body, dict) else None


def ws_url(base: str, token: str, friend_id: str) -> str:
    parts = urlsplit(base)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return f"{scheme}://{parts.netloc}/ws/chat?token={quote(token)}&friendId={quote(friend_id)}"


def open_socket(base: str, token: str, friend_id: str) -> tuple[ClientConnection | None, str]:
    """Devuelve (socket, motivo). El motivo nunca incluye la URL ni el token."""
    try:
        ws = connect(ws_url(base, token, friend_id), open_timeout=TIMEOUT, close_timeout=2)
        first = json.loads(ws.recv(timeout=TIMEOUT))
    except ConnectionClosed as exc:
        code = exc.rcvd.code if exc.rcvd else "?"
        return None, f"cerrado por el servidor (código {code})"
    except (WebSocketException, OSError, TimeoutError, ValueError) as exc:
        return None, type(exc).__name__
    if first.get("event") != "connected":
        ws.close()
        return None, "primer frame distinto de 'connected'"
    return ws, ""


def wait_event(ws: ClientConnection, event: str, check: Callable[[dict], bool]) -> float | None:
    """Instante (perf_counter) en que llega el frame esperado, o None si vence el tiempo."""
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        try:
            frame = json.loads(ws.recv(timeout=max(0.1, deadline - time.monotonic())))
        except (TimeoutError, ConnectionClosed, ValueError):
            return None
        if frame.get("event") == "error":
            return None
        if frame.get("event") == event and check(frame.get("data") or {}):
            return time.perf_counter()
    return None


def exchange(label: str, sender: ClientConnection, receiver: ClientConnection, recipient_id: str) -> bool:
    body = f"smoke-{uuid.uuid4().hex[:8]}"
    client_id = str(uuid.uuid4())
    frame = {"event": "message:send", "data": {"clientMessageId": client_id, "recipientId": recipient_id, "body": body}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        started = time.perf_counter()
        ack = pool.submit(wait_event, sender, "message:ack", lambda d: d.get("clientMessageId") == client_id and d.get("body") == body)
        new = pool.submit(wait_event, receiver, "message:new", lambda d: d.get("body") == body)
        sender.send(json.dumps(frame))
        ack_at, new_at = ack.result(), new.result()
    ok_new = report(
        new_at is not None, f"{label}: el destinatario recibe message:new", started=started, until=new_at
    )
    ok_ack = report(ack_at is not None, f"{label}: el emisor recibe message:ack", started=started, until=ack_at)
    return ok_new and ok_ack


def history_has(base: str, token: str, friend_id: str, minimum: int) -> bool:
    status, body = http_json("GET", f"{base}/api/v1/conversations/{friend_id}/messages?limit=50", token)
    return status == 200 and isinstance(body, dict) and len(body.get("items", [])) >= minimum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python-base", default="http://127.0.0.1:3000", help="API Python local")
    parser.add_argument("--public-origin", required=True, help="origen público de CloudFront (llega a Node)")
    parser.add_argument("--email-a", help="correo de A (se pregunta si se omite)")
    parser.add_argument("--email-b", help="correo de B (se pregunta si se omite)")
    args = parser.parse_args()
    python_base, node_base = args.python_base.rstrip("/"), args.public_origin.rstrip("/")

    email_a = args.email_a or input("Correo de A (Python): ").strip()
    email_b = args.email_b or input("Correo de B (Node): ").strip()
    password_a = getpass.getpass("Contraseña de A (no se muestra): ")
    password_b = getpass.getpass("Contraseña de B (no se muestra): ")

    started = time.perf_counter()
    token_a = login(python_base, email_a, password_a)
    del password_a
    if not report(token_a is not None, "login de A en la API Python", started=started):
        return 1
    started = time.perf_counter()
    token_b = login(node_base, email_b, password_b)
    del password_b
    if not report(token_b is not None, "login de B en el origen público (Node)", started=started):
        return 1

    id_a, id_b = user_id(python_base, token_a), user_id(node_base, token_b)
    if not report(bool(id_a and id_b), "obtener userId de A y B (GET /me)"):
        return 1

    started = time.perf_counter()
    ws_a, reason_a = open_socket(python_base, token_a, id_b)
    report(ws_a is not None, "A conecta al WebSocket de Python", reason_a, started)
    started = time.perf_counter()
    ws_b, reason_b = open_socket(node_base, token_b, id_a)
    report(ws_b is not None, "B conecta al WebSocket de Node", reason_b, started)
    if ws_a is None or ws_b is None:
        for ws in (ws_a, ws_b):
            if ws is not None:
                ws.close()
        return 1

    try:
        exchange("Python → Node (A→B)", ws_a, ws_b, id_b)
        exchange("Node → Python (B→A)", ws_b, ws_a, id_a)
    finally:
        ws_a.close()
        ws_b.close()

    report(history_has(python_base, token_a, id_b, 2), "historial en RDS visible por Python (>= 2 mensajes)")
    report(history_has(node_base, token_b, id_a, 2), "historial en RDS visible por Node (>= 2 mensajes)")
    print("\nRESULTADO:", "OK" if failures == 0 else f"FALLO ({failures} paso(s))")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
