"""Almacén EN MEMORIA de retos faciales (login facial, PRO-14).

Guarda, por ``challengeId``, la ``Session`` de Cognito entre ``POST /auth/face/challenges`` y
``POST /auth/face/challenges/{id}/verify`` (el ALB no tiene afinidad y el cliente solo reenvía ``challengeId`` y
``captureKey``). Es válido únicamente porque ``/api/v1/auth/face*`` se enruta a UNA instancia con UN proceso de
uvicorn (docs/api/python-face-login.md §3): con dos procesos o dos instancias, un verify podría caer donde no
está el reto y responder 404. Se pierde al reiniciar el servicio.

Nunca se registra su contenido (correo, Session, token de subida) y ``repr`` lo oculta.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from app.common.errors import ApiError

DEFAULT_MAX_ENTRIES = 1000


@dataclass(frozen=True)
class FaceChallenge:
    challenge_id: str
    # Username interno que Cognito devuelve en ChallengeParameters (o el correo si falta).
    username: str = field(repr=False)
    # ``None`` marca un reto falso (anti-enumeración): el verify siempre da 422 y nunca llama a Cognito.
    session: str | None = field(repr=False)
    upload_token: str = field(repr=False)
    expires_at: float  # en la escala del reloj del almacén


class FaceChallengeStore:
    def __init__(self, *, max_entries: int = DEFAULT_MAX_ENTRIES, clock: Callable[[], float] = time.monotonic) -> None:
        if max_entries < 1:
            raise ValueError("max_entries debe ser positivo")
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._items: OrderedDict[str, FaceChallenge] = OrderedDict()

    def now(self) -> float:
        return self._clock()

    def add(self, challenge: FaceChallenge) -> None:
        """Agrega un reto. Con el tope alcanzado (tras limpiar caducados) responde 429 sin desalojar a nadie."""
        with self._lock:
            self._purge_expired()
            if challenge.challenge_id not in self._items and len(self._items) >= self._max_entries:
                raise ApiError(429, "RATE_LIMITED")
            self._items[challenge.challenge_id] = challenge

    def take(self, challenge_id: str) -> FaceChallenge | None:
        """Saca el reto de forma atómica (un reto se usa una sola vez). ``None`` si no existe o venció."""
        with self._lock:
            challenge = self._items.pop(challenge_id, None)
            if challenge is None or challenge.expires_at <= self._clock():
                return None
            return challenge

    def put_back(self, challenge: FaceChallenge) -> None:
        """Devuelve un reto que no llegó a consumirse (p. ej. 429 de Cognito antes de invocar al trigger)."""
        with self._lock:
            if challenge.expires_at > self._clock():
                self._items[challenge.challenge_id] = challenge

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._items)

    def _purge_expired(self) -> None:
        now = self._clock()
        for key in [k for k, c in self._items.items() if c.expires_at <= now]:
            del self._items[key]
