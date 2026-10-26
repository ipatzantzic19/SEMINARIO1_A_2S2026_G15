"""Registro de conexiones WebSocket de ESTA instancia y entrega local (PRO-16).

Todo ocurre en el event loop (sin hilos): no hay bloqueos entre sesiones.
Las notificaciones de LISTEN se encolan y las procesa una sola tarea, de modo
que el orden de llegada de PostgreSQL se conserva en cada socket.

Reglas de entrega (idénticas a ChatGateway.handleNotification de Node):
- ``message:ack`` a los sockets del EMISOR cuya conversación es con el destinatario.
- ``message:new`` a los sockets del DESTINATARIO cuya conversación es con el emisor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger("semisocial.chat")

SEND_TIMEOUT_SECONDS = 5.0
_REQUIRED_FIELDS = ("messageId", "senderId", "recipientId", "body", "createdAt")


class ChatSession:
    def __init__(self, websocket: WebSocket, user_id: str, friend_id: str) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.friend_id = friend_id
        self._lock = asyncio.Lock()  # un frame a la vez por socket

    async def send(self, frame: dict[str, Any]) -> bool:
        if self.websocket.application_state != WebSocketState.CONNECTED:
            return False
        text = json.dumps(frame, ensure_ascii=False, separators=(",", ":"))
        try:
            async with self._lock:
                await asyncio.wait_for(self.websocket.send_text(text), SEND_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 - socket roto o lento: se descarta, el handler lo limpiará
            return False
        return True


class ChatHub:
    def __init__(self) -> None:
        self._sessions: dict[str, set[ChatSession]] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    @property
    def connection_count(self) -> int:
        return sum(len(sessions) for sessions in self._sessions.values())

    # -- sesiones -------------------------------------------------------------

    def add(self, session: ChatSession) -> None:
        self._sessions.setdefault(session.user_id, set()).add(session)

    def remove(self, session: ChatSession) -> None:
        sessions = self._sessions.get(session.user_id)
        if sessions is None:
            return
        sessions.discard(session)
        if not sessions:
            del self._sessions[session.user_id]

    async def close_all(self, code: int = 1001) -> None:
        sessions = [s for group in self._sessions.values() for s in group]
        self._sessions.clear()
        for session in sessions:
            try:
                await session.websocket.close(code=code)
            except Exception:  # noqa: BLE001 - ya cerrado
                pass

    # -- difusión -----------------------------------------------------------------

    def enqueue(self, raw_payload: str) -> None:
        """Llamado en el event loop por el listener; no bloquea."""
        self._queue.put_nowait(raw_payload)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._consume(), name="chat-hub-dispatch")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.close_all()

    async def _consume(self) -> None:
        while True:
            raw = await self._queue.get()
            try:
                await self.dispatch(raw)
            except Exception as exc:  # noqa: BLE001 - un payload malo no detiene la entrega
                logger.error("chat.dispatch_error", extra={"event": "chat.dispatch_error", "errorType": type(exc).__name__})

    async def dispatch(self, raw_payload: str) -> None:
        try:
            payload = json.loads(raw_payload)
        except ValueError:
            payload = None
        if not isinstance(payload, dict) or not all(isinstance(payload.get(k), str) for k in _REQUIRED_FIELDS):
            # Nunca se registra el contenido de un payload inválido.
            logger.warning("chat.bad_notification", extra={"event": "chat.bad_notification"})
            return

        sender, recipient = payload["senderId"], payload["recipientId"]
        common = {key: payload[key] for key in _REQUIRED_FIELDS if key != "messageId"}
        deliveries: list[Any] = []

        client_id = payload.get("clientMessageId")
        ack: dict[str, Any] = {"messageId": payload["messageId"], **common}
        if isinstance(client_id, str):
            ack = {"clientMessageId": client_id, **ack}
        for session in tuple(self._sessions.get(sender, ())):
            if session.friend_id == recipient:
                deliveries.append(session.send({"event": "message:ack", "data": ack}))

        new = {"messageId": payload["messageId"], **common, "readAt": None}
        for session in tuple(self._sessions.get(recipient, ())):
            if session.friend_id == sender:
                deliveries.append(session.send({"event": "message:new", "data": new}))

        if deliveries:
            await asyncio.gather(*deliveries)
