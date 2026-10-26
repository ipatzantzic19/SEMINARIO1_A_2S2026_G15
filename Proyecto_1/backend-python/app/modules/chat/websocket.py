"""WebSocket ``/ws/chat`` (PRO-16). Protocolo: docs/api/python-chat.md.

Va fuera de ``/api/v1``, igual que Node, y también en ``<API_BASE_PATH>/chat/ws``
(alias de Node). ``?token=<access token>&friendId=<uuid>``.

Como Node, el upgrade se ACEPTA y después se cierra con el código de la
política (4400/4401/4403/1011): si se cerrara antes del ``accept``, uvicorn
respondería HTTP 403 y el frontend (que solo corta el reintento con 4400, 4401,
4403 y 1000) vería 1006 y reintentaría. La única excepción es la falta de RDS
o de difusión, que se rechaza antes del ``accept`` con HTTP 503.

Nunca se registran el token (va en la URL), el friendId ni el contenido.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.common.errors import error_body
from app.modules.chat.hub import ChatHub, ChatSession
from app.modules.chat.listener import ChatListener
from app.modules.chat.service import ChatError, ChatIdentity, ChatService, HandshakeRejected

logger = logging.getLogger("semisocial.chat")

# 4000 caracteres de hasta 4 bytes + sobre JSON + escapes \uXXXX caben de sobra.
MAX_FRAME_BYTES = 64 * 1024


async def _deny_unavailable(websocket: WebSocket) -> None:
    body = error_body(str(uuid.uuid4()), "SERVICE_UNAVAILABLE", "Servicio no disponible.")
    if "websocket.http.response" in websocket.scope.get("extensions", {}):
        await websocket.send_denial_response(JSONResponse(body, status_code=503))
    else:  # servidor sin la extensión: el cierre previo al accept equivale a un rechazo
        await websocket.close(code=1013)


def _error_frame(code: str, message: str, client_message_id: str | None = None) -> dict:
    data = {"code": code, "message": message}
    if client_message_id is not None:
        data["clientMessageId"] = client_message_id
    return {"event": "error", "data": data}


async def chat_socket(websocket: WebSocket) -> None:
    state = websocket.app.state
    service: ChatService = state.chat_service
    hub: ChatHub = state.chat_hub
    listener: ChatListener | None = state.chat_listener

    # Sin RDS (o sin difusión LISTEN activa) no hay chat: 503, sin respaldo en memoria.
    if not state.database.configured or listener is None or not listener.ready:
        await _deny_unavailable(websocket)
        return

    await websocket.accept()
    try:
        identity = await run_in_threadpool(
            service.authorize,
            websocket.query_params.get("token"),
            websocket.query_params.get("friendId"),
        )
    except HandshakeRejected as rejected:
        await websocket.close(code=rejected.code, reason=rejected.reason)
        return

    session = ChatSession(websocket, identity.user_id, identity.friend_id)
    hub.add(session)
    try:
        logger.info("chat.connected", extra={"event": "chat.connected"})
        await session.send({"event": "connected", "data": {"userId": identity.user_id, "friendId": identity.friend_id}})
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            raw = message.get("text")
            if raw is None:
                raw = (message.get("bytes") or b"").decode("utf-8", errors="replace")
            if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
                await websocket.close(code=1009, reason="Message too big")
                break
            await _handle_frame(session, service, listener, raw)
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(session)
        logger.info("chat.disconnected", extra={"event": "chat.disconnected"})


async def _handle_frame(session: ChatSession, service: ChatService, listener: ChatListener, raw: str) -> None:
    try:
        frame = json.loads(raw)
    except ValueError:
        await session.send(_error_frame("VALIDATION_ERROR", "El frame transmitido debe ser un JSON válido."))
        return
    if not isinstance(frame, dict):
        return
    event = frame.get("event")

    if event == "ping":
        await session.send({"event": "pong"})
        return
    if event != "message:send":
        return  # Node registra y descarta los eventos desconocidos.

    data = frame.get("data")
    client_id = data.get("clientMessageId") if isinstance(data, dict) else None
    client_id = client_id if isinstance(client_id, str) and len(client_id) <= 64 else None
    if not listener.ready:
        # Sin LISTEN activo el mensaje se guardaría pero nadie recibiría el ack: se rechaza antes.
        await session.send(_error_frame("SERVICE_UNAVAILABLE", "Chat temporalmente no disponible.", client_id))
        return
    identity = ChatIdentity(user_id=session.user_id, friend_id=session.friend_id)
    try:
        await run_in_threadpool(service.send, identity, data)
    except ChatError as error:
        await session.send(_error_frame(error.code, error.message, error.client_message_id))
    # Éxito: sin respuesta directa; el ack llega por LISTEN/NOTIFY (hub.dispatch).


def register(app: FastAPI, api_base_path: str) -> None:
    app.add_api_websocket_route("/ws/chat", chat_socket, name="chat_ws")
    app.add_api_websocket_route(f"{api_base_path}/chat/ws", chat_socket, name="chat_ws_alias")
