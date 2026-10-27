"""Login facial con Cognito CUSTOM_AUTH (PRO-14). Detalle y límites: docs/api/python-face-login.md.

Python NO emite sesión propia: crea el reto con ``InitiateAuth`` (CUSTOM_AUTH), guarda la ``Session`` en
memoria (``FaceChallengeStore``) y, al verificar, la devuelve a Cognito con ``RespondToAuthChallenge``; los
tokens son los que emite Cognito. La comparación facial la hace el trigger VerifyAuthChallengeResponse
(lambdas/cognito-facial) con Rekognition.

Logs: solo eventos y motivos estables; nunca correo, Session, ``uploadToken``, claves de S3, tokens ni el
``challengeAnswer``.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.common.errors import ApiError
from app.modules.auth.face_upload_token import FaceUploadTokenSigner
from app.modules.auth.face_store import FaceChallenge, FaceChallengeStore
from app.modules.auth.service import AuthService
from app.modules.integrations.cognito.gateway import FACE_UNKNOWN_USER, AuthChallenge, AuthTokens
from app.modules.users.directory import log_event

DEFAULT_TTL_SECONDS = 120
MIN_TTL_SECONDS = 30
MAX_TTL_SECONDS = 300
MAX_CAPTURE_KEY_LENGTH = 1024
# Lo que sigue al prefijo: el nombre que genera la Lambda de upload (uuid + extensión); nada de subcarpetas.
_CAPTURE_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _invalid_capture() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_ERROR",
        "La clave de la captura no es válida.",
        details={"reason": "INVALID_CAPTURE_KEY"},
    )


def _ttl_from(parameters: dict[str, str]) -> int:
    try:
        ttl = int(parameters.get("expiresInSeconds", ""))
    except ValueError:
        return DEFAULT_TTL_SECONDS
    return max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, ttl))


class FaceLoginService:
    def __init__(
        self,
        cognito: Any,
        auth: AuthService,
        store: FaceChallengeStore,
        capture_prefix: str,
        *,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        token_factory: Callable[[str, int, int], str] | None = None,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._cognito = cognito
        self._auth = auth
        self._store = store
        self._capture_prefix = capture_prefix
        self._wall_clock = wall_clock
        self._token_factory = token_factory or FaceUploadTokenSigner(None, None).issue
        self._id_factory = id_factory

    # -- POST /auth/face/challenges ------------------------------------------

    def create_challenge(self, *, email: str) -> dict[str, Any]:
        try:
            outcome = self._cognito.initiate_custom_auth(email)
        except ApiError as exc:
            if isinstance(exc.details, dict) and exc.details.get("reason") == FACE_UNKNOWN_USER:
                return self._decoy("UNKNOWN_USER")
            # Sin referencia (400), cuenta sin confirmar (401), 429 y 503: igual que el login por contraseña.
            raise

        challenge_id = outcome.parameters.get("challengeId") if isinstance(outcome, AuthChallenge) else None
        if not isinstance(outcome, AuthChallenge) or outcome.name != "CUSTOM_CHALLENGE" or not challenge_id:
            return self._decoy("UNEXPECTED_CHALLENGE")

        ttl = _ttl_from(outcome.parameters)
        body = self._save_challenge(challenge_id, outcome.parameters.get("USERNAME") or email, outcome.session, ttl)
        log_event("face.challenge_created")
        return body

    def _decoy(self, reason: str) -> dict[str, Any]:
        """El señuelo tiene el mismo token firmado y forma de respuesta que un reto real."""
        body = self._save_challenge(self._id_factory(), "", None, DEFAULT_TTL_SECONDS)
        log_event("face.challenge_decoy", reason=reason)
        return body

    def _save_challenge(self, challenge_id: str, username: str, session: str | None, ttl: int) -> dict[str, Any]:
        now = self._wall_clock().timestamp()
        issued_at = int(now)
        expires_at = issued_at + ttl
        upload_token = self._token_factory(challenge_id, issued_at, ttl)
        # El vencimiento del almacén, la respuesta y el JWT representan el mismo instante.
        self._store.add(FaceChallenge(
            challenge_id=challenge_id,
            username=username,
            session=session,
            upload_token=upload_token,
            expires_at=self._store.now() + (expires_at - now),
        ))
        return {
            "challengeId": challenge_id,
            "expiresAt": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "uploadToken": upload_token,
        }

    # -- POST /auth/face/challenges/{challengeId}/verify ------------------------

    def verify(self, *, challenge_id: str, capture_key: str) -> dict[str, Any]:
        self._validate_capture_key(challenge_id, capture_key)

        # Un reto se consume una sola vez, también ante dos verify simultáneos.
        challenge = self._store.take(challenge_id)
        if challenge is None:
            log_event("face.challenge_unknown")
            raise ApiError(404, "NOT_FOUND", "El desafío facial no existe o venció.")
        if challenge.session is None:
            log_event("face.not_matched", reason="DECOY")
            raise ApiError(422, "FACE_NOT_MATCHED")

        answer = json.dumps(
            {"challengeId": challenge_id, "purpose": "faceCapture", "captureKey": capture_key},
            separators=(",", ":"),
        )
        try:
            outcome = self._cognito.respond_to_custom_challenge(
                username=challenge.username, session=challenge.session, answer=answer
            )
        except ApiError as exc:
            if exc.status_code == 429:
                # Cognito limitó la llamada antes de invocar al trigger: el reto sigue intacto.
                self._store.put_back(challenge)
            log_event("face.not_matched" if exc.status_code == 422 else "face.verify_failed", reason=str(exc.status_code))
            raise

        if isinstance(outcome, AuthTokens):
            response = self._auth.token_response(outcome)
            log_event("face.verified")
            return response
        # Otro CUSTOM_CHALLENGE: no coincide y Cognito ofrece reintentar con un reto nuevo. Se descarta; el
        # usuario reinicia el flujo (decisión 2: todo verify fallido elimina el reto).
        log_event("face.not_matched", reason="RETRY_CHALLENGE")
        raise ApiError(422, "FACE_NOT_MATCHED")

    def _validate_capture_key(self, challenge_id: str, capture_key: str) -> None:
        prefix = f"{self._capture_prefix}{challenge_id}/"
        if (
            len(capture_key) > MAX_CAPTURE_KEY_LENGTH
            or ".." in capture_key
            or not capture_key.startswith(prefix)
            or not _CAPTURE_FILE_RE.match(capture_key[len(prefix):])
        ):
            raise _invalid_capture()
