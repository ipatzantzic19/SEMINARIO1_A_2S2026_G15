"""ChatListener: LISTEN en conexión dedicada, reconexión con espera creciente, cierre limpio (PRO-16)."""

from __future__ import annotations

import asyncio
import threading
import time

from app.modules.chat.listener import ChatListener
from tests.chat_fakes import FakeChatBus


async def eventually(condition, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condición no cumplida a tiempo")


def make(bus: FakeChatBus, received: list[str], **kwargs) -> ChatListener:
    options = {"poll_seconds": 0.05, "min_backoff": 0.05, "max_backoff": 0.4, **kwargs}
    return ChatListener(bus.connect, received.append, **options)


def test_receives_payloads_on_the_event_loop() -> None:
    async def scenario() -> None:
        bus, received = FakeChatBus(), []
        listener = make(bus, received)
        listener.start()
        await eventually(lambda: listener.ready)
        bus.publish("uno")
        bus.publish("dos")
        await eventually(lambda: received == ["uno", "dos"])
        await listener.stop()

    asyncio.run(scenario())


def test_uses_one_dedicated_connection_and_listens_before_ready() -> None:
    async def scenario() -> None:
        bus = FakeChatBus()
        listener = make(bus, [])
        listener.start()
        await eventually(lambda: listener.ready)
        assert bus.connect_attempts == 1 and bus.connections[0].listening
        await listener.stop()

    asyncio.run(scenario())


def test_reconnects_with_growing_backoff_after_failures() -> None:
    async def scenario() -> None:
        bus, received = FakeChatBus(), []
        times: list[float] = []
        original = bus.connect

        def timed():
            times.append(time.monotonic())
            return original()

        bus.fail_connects = 3
        listener = ChatListener(
            timed, received.append, poll_seconds=0.05, min_backoff=0.05, max_backoff=0.4
        )
        listener.start()
        await eventually(lambda: listener.ready)
        assert not listener.ready or bus.connect_attempts == 4
        gaps = [b - a for a, b in zip(times, times[1:])]
        assert len(gaps) == 3
        # 0,05 s → 0,1 s → 0,2 s (con holgura de planificación)
        assert gaps[0] >= 0.045 and gaps[1] >= 0.09 and gaps[2] >= 0.18
        assert gaps[2] > gaps[0] * 2
        bus.publish("tras-reconectar")
        await eventually(lambda: received == ["tras-reconectar"])
        await listener.stop()

    asyncio.run(scenario())


def test_backoff_is_capped() -> None:
    async def scenario() -> None:
        bus = FakeChatBus()
        times: list[float] = []
        original = bus.connect

        def timed():
            times.append(time.monotonic())
            return original()

        bus.fail_connects = 6
        listener = ChatListener(timed, lambda _p: None, poll_seconds=0.05, min_backoff=0.02, max_backoff=0.08)
        listener.start()
        await eventually(lambda: listener.ready, timeout=5)
        gaps = [b - a for a, b in zip(times, times[1:])]
        assert max(gaps) < 0.08 + 0.25  # nunca supera el tope (más holgura de planificación)
        await listener.stop()

    asyncio.run(scenario())


def test_not_ready_while_the_database_is_down() -> None:
    async def scenario() -> None:
        bus = FakeChatBus()
        bus.fail_connects = 10_000
        listener = make(bus, [])
        listener.start()
        await asyncio.sleep(0.2)
        assert not listener.ready and bus.connect_attempts >= 2
        await listener.stop()

    asyncio.run(scenario())


def test_reconnects_after_a_dropped_connection() -> None:
    async def scenario() -> None:
        bus, received = FakeChatBus(), []
        listener = make(bus, received)
        listener.start()
        await eventually(lambda: listener.ready)
        bus.drop_connections()
        await eventually(lambda: bus.connect_attempts >= 2 and listener.ready)
        assert bus.connections[0].closed  # la conexión rota se cierra antes de reconectar
        bus.publish("despues")
        await eventually(lambda: received == ["despues"])
        await listener.stop()

    asyncio.run(scenario())


def test_stop_closes_the_connection_and_ends_the_thread() -> None:
    async def scenario() -> None:
        bus = FakeChatBus()
        listener = make(bus, [])
        listener.start()
        await eventually(lambda: listener.ready)
        started = time.monotonic()
        await listener.stop()
        assert time.monotonic() - started < 2
        assert not listener.ready and bus.connections[0].closed
        assert not [t for t in threading.enumerate() if t.name.startswith("chat-listen") and t.is_alive()]
        bus.publish("tarde")  # ya nadie escucha

    asyncio.run(scenario())


def test_stop_during_backoff_does_not_wait_the_full_delay() -> None:
    async def scenario() -> None:
        bus = FakeChatBus()
        bus.fail_connects = 10_000
        listener = make(bus, [], min_backoff=30, max_backoff=30)
        listener.start()
        await asyncio.sleep(0.1)
        started = time.monotonic()
        await listener.stop()
        assert time.monotonic() - started < 2

    asyncio.run(scenario())


def test_app_lifespan_starts_and_stops_the_listener(build_app) -> None:
    from fastapi.testclient import TestClient

    from tests.chat_world import make_world, wait_ready

    world = make_world(build_app)
    app = world.apps[0]
    assert app.state.chat_listener is None
    with TestClient(app):
        wait_ready(app)
        listener = app.state.chat_listener
        assert world.bus.connections[0].listening
    assert world.bus.connections[0].closed and app.state.chat_listener is None and not listener.ready
