"""Perfil propio: GET /me, PATCH /me y POST /me/complete-profile (PRO-14).

Foto de perfil: la Lambda de PRO-11 escribe la foto pública y su copia privada
con el mismo nombre (``public/{sub}/{uuid}.{ext}`` y ``references/{sub}/...``).
El cliente solo envía la clave pública; el servidor comprueba que pertenece al
``sub`` del token, deriva la referencia y verifica ambas con HeadObject.

PATCH /me: verifica ``currentPassword`` con InitiateAuth y sincroniza Cognito
dentro de la transacción de RDS (si Cognito falla, ROLLBACK). Si el COMMIT
falla después de Cognito, se revierte Cognito con los valores anteriores.

Login facial: tras guardar la referencia en RDS (complete-profile y PATCH /me con foto nueva) se escribe
``custom:face_reference_key`` en Cognito con AdminUpdateUserAttributes (rol del backend). Es "mejor esfuerzo":
si falla se registra ``face.reference_sync_failed`` y la operación NO falla (docs/api/python-face-login.md §6).
Detalle: docs/api/python-auth.md §5–§6.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.common.auth import Principal
from app.common.errors import ApiError, ForbiddenError, ServiceUnavailableError
from app.config import S3Settings
from app.modules.integrations.cognito.gateway import MSG_INVALID_CURRENT_PASSWORD, AuthChallenge
from app.modules.integrations.uploads import ALLOWED_MIME_TYPES, MAX_IMAGE_BYTES
from app.modules.users.directory import UserDirectory, conflict_error, log_event
from app.modules.users.repository import DuplicateUser, InvalidUserData, ProfileChanges, SyncCommitFailed

# Nombre de archivo que genera la Lambda: randomUUID() + extensión por MIME
# (lambdas/image-upload/index.js y multipart.js getExtensionForMime).
_FILE_NAME = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:jpg|png|webp)"


@dataclass(frozen=True)
class ProfileUpdate:
    current_password: str
    full_name: str | None = None
    dpi: str | None = None
    profile_image_key: str | None = None


def _bad_request(message: str, reason: str) -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", message, details={"reason": reason})


class ProfileService:
    def __init__(self, directory: UserDirectory, images: Any, s3: S3Settings) -> None:
        self._directory = directory
        self._users = directory.users
        self._cognito = directory.cognito
        self._images = images
        self._s3 = s3
        self._public_key_re = re.compile(rf"^{re.escape(s3.profile_prefix)}(?P<sub>[^/]+)/(?P<file>{_FILE_NAME})$")

    # -- GET /me -----------------------------------------------------------

    def get(self, principal: Principal, access_token: str) -> dict[str, Any]:
        record = self._directory.get_or_reconcile(principal.sub, access_token)
        return self._directory.profile_payload(record)

    # -- POST /me/complete-profile -----------------------------------------

    def complete(self, principal: Principal, access_token: str, profile_image_key: str) -> dict[str, Any]:
        record = self._directory.get_or_reconcile(principal.sub, access_token)
        if record.profile_complete:
            raise ApiError(409, "CONFLICT", "El perfil ya está completo.", details={"reason": "PROFILE_ALREADY_COMPLETE"})

        public_key, reference_key = self._verified_image(principal.sub, profile_image_key)
        try:
            updated = self._directory.call(
                lambda: self._users.complete_profile(principal.sub, public_key, reference_key)
            )
        except InvalidUserData:
            # El prefijo configurado no coincide con el CHECK de la BD.
            log_event("profile.complete_rejected_by_db", logging.ERROR, reason="CHECK_VIOLATION")
            raise ServiceUnavailableError() from None
        if updated is None:  # otra solicitud lo completó en paralelo
            raise ApiError(409, "CONFLICT", "El perfil ya está completo.", details={"reason": "PROFILE_ALREADY_COMPLETE"})
        self._sync_face_reference(principal.sub, reference_key)
        log_event("profile.completed")
        return self._directory.profile_payload(updated)

    # -- PATCH /me ---------------------------------------------------------

    def update(self, principal: Principal, change: ProfileUpdate) -> dict[str, Any]:
        record = self._directory.call(lambda: self._users.get_by_sub(principal.sub))
        if record is None or not record.profile_complete:
            raise ForbiddenError("Complete su perfil para usar esta funcionalidad.", details={"reason": "PROFILE_INCOMPLETE"})

        fresh_token = self._reauthenticate(principal, record.email, change.current_password)

        full_name = change.full_name if change.full_name not in (None, record.full_name) else None
        dpi = change.dpi if change.dpi not in (None, record.dpi) else None
        image_key = reference_key = None
        if change.profile_image_key is not None and change.profile_image_key != record.profile_image_key:
            image_key, reference_key = self._verified_image(principal.sub, change.profile_image_key)

        if dpi is not None and self._directory.call(
            lambda: self._users.find_conflicts(dpi=dpi, exclude_sub=principal.sub)
        ):
            raise conflict_error("dpi")

        if full_name is None and dpi is None and image_key is None:
            log_event("profile.update_noop")
            return self._directory.profile_payload(record)

        def sync_cognito() -> None:
            # La foto no vive en Cognito; solo nombre y DPI.
            if full_name is not None or dpi is not None:
                self._cognito.update_attributes(fresh_token, full_name=full_name, dpi=dpi)

        changes = ProfileChanges(full_name=full_name, dpi=dpi, profile_image_key=image_key, face_reference_key=reference_key)
        try:
            updated = self._directory.call(lambda: self._users.update_profile(principal.sub, changes, sync_cognito))
        except DuplicateUser as exc:
            raise conflict_error(exc.field) from None
        except InvalidUserData:
            log_event("profile.update_rejected_by_db", logging.ERROR, reason="CHECK_VIOLATION")
            raise ServiceUnavailableError() from None
        except SyncCommitFailed:
            self._revert_cognito(principal.sub, fresh_token, full_name and record.full_name, dpi and record.dpi)
            raise ServiceUnavailableError() from None
        if updated is None:
            raise ServiceUnavailableError()
        if reference_key is not None:
            self._sync_face_reference(principal.sub, reference_key)
        log_event("profile.updated")
        return self._directory.profile_payload(updated)

    # -- auxiliares --------------------------------------------------------

    def _reauthenticate(self, principal: Principal, email: str, password: str) -> str:
        outcome = self._cognito.password_auth(email, password, reauthentication=True)
        if isinstance(outcome, AuthChallenge):
            raise _bad_request("No fue posible confirmar la contraseña actual.", "REAUTHENTICATION_CHALLENGE")
        issued = self._directory.verify_issued(outcome.access_token)
        if issued.sub != principal.sub:
            # El correo de RDS apunta a otra identidad de Cognito: no se cambia nada.
            log_event("profile.reauth_sub_mismatch", logging.ERROR, cognitoSub=principal.sub)
            raise _bad_request(MSG_INVALID_CURRENT_PASSWORD, "INVALID_CURRENT_PASSWORD")
        return outcome.access_token

    def _verified_image(self, sub: str, profile_image_key: str) -> tuple[str, str]:
        match = self._public_key_re.match(profile_image_key)
        if match is None:
            raise _bad_request("La clave de la foto no es válida.", "INVALID_IMAGE_KEY")
        if match["sub"] != sub:
            raise ForbiddenError("La foto no pertenece a su cuenta.", details={"reason": "IMAGE_KEY_NOT_OWNED"})
        reference_key = f"{self._s3.face_reference_prefix}{sub}/{match['file']}"

        public = self._images.head(profile_image_key)
        if public is None:
            raise _bad_request("No se encontró la foto cargada.", "PROFILE_IMAGE_NOT_FOUND")
        if public.content_type not in ALLOWED_MIME_TYPES or (public.content_length or 0) > MAX_IMAGE_BYTES:
            raise _bad_request("La foto cargada no es una imagen válida.", "PROFILE_IMAGE_INVALID")
        if self._images.head(reference_key) is None:
            raise _bad_request("No se encontró la referencia facial de la foto.", "FACE_REFERENCE_NOT_FOUND")
        return profile_image_key, reference_key

    def _sync_face_reference(self, sub: str, reference_key: str) -> None:
        """custom:face_reference_key en Cognito; nunca hace fallar la operación ni registra la clave."""
        try:
            self._cognito.update_face_reference(sub, reference_key)
        except ApiError as exc:
            # RDS ya tiene la referencia: el perfil queda completo; el login facial fallará con
            # FACE_REFERENCE_MISSING hasta que se escriba el atributo (a mano o repitiendo la edición de foto).
            log_event("face.reference_sync_failed", logging.WARNING, reason=str(exc.status_code))
            return
        log_event("face.reference_synced")

    def _revert_cognito(self, sub: str, token: str, old_name: str | None, old_dpi: str | None) -> None:
        try:
            self._cognito.update_attributes(token, full_name=old_name or None, dpi=old_dpi or None)
            log_event("profile.cognito_reverted", logging.ERROR, reason="COMMIT_FAILED", cognitoSub=sub)
        except ApiError:
            log_event("profile.cognito_revert_failed", logging.CRITICAL, reason="COMMIT_FAILED", cognitoSub=sub)
