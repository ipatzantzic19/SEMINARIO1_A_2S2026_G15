"""Suscripción LISTEN a ``chat_messages`` en una conexión DEDICADA (PRO-16).

- La conexión NO sale del pool: LISTEN exige una sesión fija y en modo
  autocommit. Es psycopg síncrono en un hilo propio (el modo asíncrono de
  psycopg no funciona con el ProactorEventLoop de Windows; ver app/database.py).
- ``run()`` es la tarea en segundo plano del lifespan: reconecta con espera
  creciente (1 s, 2 s, 4 s… hasta 30 s; se reinicia tras una conexión sana).
- ``stop()`` pide parar y espera al hilo (como mucho ``poll_seconds``).
- Los payloads se entregan al event loop con ``call_soon_threadsafe``; no se
  registra su contenido.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from app.modules.chat.repository import CHANNEL

logger = logging.getLogger("semisocial.chat")


class ListenConnection(Protocol):
    def listen(self, channel: str) -> None: ...

    def notifies(self, timeout: float) -> Iterator[str]:
        """Payloads recibidos; termina al pasar ``timeout`` sin notificaciones."""

    def close(self) -> None: ...


class PsycopgListenConnection:
    """Adaptador de ``psycopg.Connection`` (autocommit) a ``ListenConnection``."""

    def __init__(self, connection) -> None:  # type: ignore[no-untyped-def]
        self._conn = connection

    def listen(self, channel: str) -> None:
        # Identificador fijo (constante del módulo), no entrada de usuario.
        self._conn.execute(f"LISTEN {channel}")

    def notifies(self, timeout: float) -> Iterator[str]:
        for notification in self._conn.notifies(timeout=timeout):
            yield notification.payload

    def close(self) -> None:
        self._conn.close()


class ChatListener:
    def __init__(
        self,
        connect: Callable[[], ListenConnection],
        on_payload: Callable[[str], None],
        *,
        poll_seconds: float = 1.0,
        min_backoff: float = 1.0,
        max_backoff: float = 30.0,
    ) -> None:
        self._connect = connect
        self._on_payload = on_payload
        self._poll = poll_seconds
        self._min_backoff = min_backoff
        self._max_backoff = max_backoff
        self._stop_thread = threading.Event()
        self._stop_async: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chat-listen")
        self._ready = False
        self._healthy_once = False

    @property
    def ready(self) -> bool:
        """True mientras la sesión tiene LISTEN activo en esta instancia."""
        return self._ready

    def start(self) -> None:
        if self._task is None:
            self._stop_async = asyncio.Event()
            self._task = asyncio.get_running_loop().create_task(self.run(), name="chat-listener")

    async def stop(self) -> None:
        self._stop_thread.set()
        if self._stop_async is not None:
            self._stop_async.set()
        task, self._task = self._task, None
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=self._poll + 5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
        # El hilo ya terminó (o termina en <= poll_seconds): la espera es breve.
        await asyncio.get_running_loop().run_in_executor(None, self._executor.shutdown)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        stop = self._stop_async or asyncio.Event()
        delay = self._min_backoff
        while not self._stop_thread.is_set():
            self._healthy_once = False
            try:
                await loop.run_in_executor(self._executor, self._listen_blocking, loop)
            except Exception as exc:  # noqa: BLE001 - psycopg: el mensaje puede traer datos de conexión
                logger.warning(
                    "chat.listener_error", extra={"event": "chat.listener_error", "errorType": type(exc).__name__}
                )
            self._ready = False
            if self._stop_thread.is_set():
                break
            if self._healthy_once:
                delay = self._min_backoff
            logger.warning("chat.listener_reconnect", extra={"event": "chat.listener_reconnect"})
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, self._max_backoff)

    def _listen_blocking(self, loop: asyncio.AbstractEventLoop) -> None:
        connection = self._connect()
        try:
            connection.listen(CHANNEL)
            self._ready = True
            self._healthy_once = True
            logger.info("chat.listener_ready", extra={"event": "chat.listener_ready"})
            while not self._stop_thread.is_set():
                for payload in connection.notifies(self._poll):
                    loop.call_soon_threadsafe(self._on_payload, payload)
        finally:
            self._ready = False
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
