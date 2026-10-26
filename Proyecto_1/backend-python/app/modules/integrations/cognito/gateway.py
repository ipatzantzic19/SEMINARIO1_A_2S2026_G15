"""Operaciones de Cognito usadas por /auth/* y /me, con mapeo de errores.

- Los errores de AWS se convierten al esquema común con mensajes propios
  fijos: nunca se devuelve ni se registra el mensaje de Cognito. Única
  excepción: se lee (sin devolverlo) para detectar MISSING_FACE_REFERENCE del
  trigger del login facial.
- Cognito responde HTTP 400 a casi todo; el mapeo se hace por ``Error.Code``.
- Los logs registran solo operación, duración y código de AWS: nunca correo,
  DPI, contraseña, código de confirmación, tokens ni ``Session``.

Tabla completa y fuentes de AWS: docs/api/python-auth.md §4.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.common.errors import ApiError, ServiceUnavailableError

logger = logging.getLogger("semisocial.cognito")

# Operaciones lógicas (una misma API de AWS puede tener mapeos distintos).
SIGN_UP = "SignUp"
CONFIRM_SIGN_UP = "ConfirmSignUp"
RESEND_CODE = "ResendConfirmationCode"
LOGIN = "InitiateAuth"
REAUTHENTICATE = "InitiateAuth.reauth"
UPDATE_ATTRIBUTES = "UpdateUserAttributes"
GET_USER = "GetUser"
# Login facial (CUSTOM_AUTH, docs/api/python-face-login.md §5).
FACE_INITIATE = "InitiateAuth.face"
FACE_RESPOND = "RespondToAuthChallenge.face"
UPDATE_FACE_REFERENCE = "AdminUpdateUserAttributes.face"

# Motivos estables que el servicio facial inspecciona (nunca se muestran tal cual).
FACE_UNKNOWN_USER = "FACE_UNKNOWN_USER"
FACE_REFERENCE_MISSING = "FACE_REFERENCE_MISSING"
# El trigger CreateAuthChallenge falla con este texto si el usuario no tiene el atributo. Es el ÚNICO caso en
# que se lee el mensaje de AWS (solo para detectarlo; el mensaje no se devuelve ni se registra).
_MISSING_REFERENCE_MARKER = "MISSING_FACE_REFERENCE"
_MISSING_REFERENCE_CODE = "UserLambdaValidationException:" + _MISSING_REFERENCE_MARKER
FACE_REFERENCE_ATTRIBUTE = "custom:face_reference_key"

_RATE_LIMITED = {
    "TooManyRequestsException",
    "LimitExceededException",
    "TooManyFailedAttemptsException",
    "ThrottlingException",
}

MSG_EMAIL_TAKEN = "Ya existe una cuenta con ese correo."
MSG_PASSWORD_POLICY = (
    "La contraseña debe tener al menos 12 caracteres e incluir mayúscula, minúscula, número y símbolo."
)
MSG_BAD_CREDENTIALS = "Correo o contraseña incorrectos."
MSG_INVALID_CURRENT_PASSWORD = "La contraseña actual no es correcta. No se realizaron cambios."

# (estado HTTP, code, mensaje, reason) por operación y código de AWS.
_Rule = tuple[int, str, str | None, str | None]
_RULES: dict[str, dict[str, _Rule]] = {
    SIGN_UP: {
        "UsernameExistsException": (409, "CONFLICT", MSG_EMAIL_TAKEN, "EMAIL_TAKEN"),
        "InvalidPasswordException": (400, "VALIDATION_ERROR", MSG_PASSWORD_POLICY, "PASSWORD_POLICY"),
        "InvalidParameterException": (
            400,
            "VALIDATION_ERROR",
            "No fue posible registrar la cuenta con los datos enviados.",
            "INVALID_PARAMETER",
        ),
        "AliasExistsException": (409, "CONFLICT", MSG_EMAIL_TAKEN, "EMAIL_TAKEN"),
    },
    CONFIRM_SIGN_UP: {
        "CodeMismatchException": (
            400,
            "VALIDATION_ERROR",
            "El código de confirmación no es correcto.",
            "CODE_MISMATCH",
        ),
        "ExpiredCodeException": (400, "VALIDATION_ERROR", "El código de confirmación venció.", "CODE_EXPIRED"),
        "UserNotFoundException": (404, "NOT_FOUND", None, None),
        "NotAuthorizedException": (
            400,
            "VALIDATION_ERROR",
            "No fue posible confirmar la cuenta.",
            "CONFIRMATION_NOT_ALLOWED",
        ),
        "InvalidParameterException": (
            400,
            "VALIDATION_ERROR",
            "No fue posible confirmar la cuenta.",
            "INVALID_PARAMETER",
        ),
        "AliasExistsException": (409, "CONFLICT", MSG_EMAIL_TAKEN, "EMAIL_TAKEN"),
    },
    RESEND_CODE: {
        # Cuenta inexistente o que ya no admite otro código (confirmada): el
        # servicio los trata igual y responde 204, para no revelar si el
        # correo existe (docs/api/python-auth.md §3.3).
        "UserNotFoundException": (404, "NOT_FOUND", None, "RESEND_NOT_ALLOWED"),
        "NotAuthorizedException": (400, "VALIDATION_ERROR", None, "RESEND_NOT_ALLOWED"),
        "InvalidParameterException": (400, "VALIDATION_ERROR", None, "RESEND_NOT_ALLOWED"),
    },
    LOGIN: {
        # Con PreventUserExistenceErrors activo Cognito ya responde NotAuthorized
        # a usuarios inexistentes; con LEGACY se iguala aquí el mensaje.
        "NotAuthorizedException": (401, "UNAUTHENTICATED", MSG_BAD_CREDENTIALS, None),
        "UserNotFoundException": (401, "UNAUTHENTICATED", MSG_BAD_CREDENTIALS, None),
        "UserNotConfirmedException": (
            401,
            "UNAUTHENTICATED",
            "La cuenta aún no está confirmada. Revise el código enviado a su correo.",
            "USER_NOT_CONFIRMED",
        ),
        "PasswordResetRequiredException": (
            401,
            "UNAUTHENTICATED",
            "Debe restablecer su contraseña antes de iniciar sesión.",
            "PASSWORD_RESET_REQUIRED",
        ),
        # El cuerpo ya se validó: un parámetro inválido aquí es configuración
        # (por ejemplo USER_PASSWORD_AUTH no habilitado en el app client) → 503.
    },
    REAUTHENTICATE: {
        # Nunca 401: el frontend cierra la sesión ante cualquier 401 con Bearer.
        "NotAuthorizedException": (
            400,
            "VALIDATION_ERROR",
            MSG_INVALID_CURRENT_PASSWORD,
            "INVALID_CURRENT_PASSWORD",
        ),
        "UserNotFoundException": (
            400,
            "VALIDATION_ERROR",
            MSG_INVALID_CURRENT_PASSWORD,
            "INVALID_CURRENT_PASSWORD",
        ),
        "PasswordResetRequiredException": (
            400,
            "VALIDATION_ERROR",
            "Debe restablecer su contraseña antes de editar el perfil.",
            "PASSWORD_RESET_REQUIRED",
        ),
    },
    UPDATE_ATTRIBUTES: {
        "InvalidParameterException": (
            400,
            "VALIDATION_ERROR",
            "No fue posible actualizar el perfil con los datos enviados.",
            "INVALID_PARAMETER",
        ),
        "AliasExistsException": (409, "CONFLICT", MSG_EMAIL_TAKEN, "EMAIL_TAKEN"),
    },
    FACE_INITIATE: {
        # Usuario inexistente (o deshabilitado): el servicio responde un reto falso con la misma forma.
        "NotAuthorizedException": (401, "UNAUTHENTICATED", None, FACE_UNKNOWN_USER),
        "UserNotFoundException": (401, "UNAUTHENTICATED", None, FACE_UNKNOWN_USER),
        "UserNotConfirmedException": (
            401,
            "UNAUTHENTICATED",
            "La cuenta aún no está confirmada. Revise el código enviado a su correo.",
            "USER_NOT_CONFIRMED",
        ),
        "PasswordResetRequiredException": (
            401,
            "UNAUTHENTICATED",
            "Debe restablecer su contraseña antes de iniciar sesión.",
            "PASSWORD_RESET_REQUIRED",
        ),
        _MISSING_REFERENCE_CODE: (
            400,
            "VALIDATION_ERROR",
            "La cuenta no tiene una referencia facial registrada.",
            FACE_REFERENCE_MISSING,
        ),
    },
    FACE_RESPOND: {
        # Sin coincidencia en el último intento, sesión vencida o consumida, o usuario ya inexistente.
        # Cognito no distingue estos casos de forma fiable (y su mensaje no es contrato): todo es 422.
        "NotAuthorizedException": (422, "FACE_NOT_MATCHED", None, None),
        "UserNotFoundException": (422, "FACE_NOT_MATCHED", None, None),
    },
    GET_USER: {
        # El Bearer ya pasó la firma, pero Cognito lo rechaza (revocado o usuario
        # eliminado): la sesión no es válida.
        "NotAuthorizedException": (401, "UNAUTHENTICATED", None, None),
        "UserNotFoundException": (401, "UNAUTHENTICATED", None, None),
    },
}


@dataclass(frozen=True)
class SignUpResult:
    sub: str
    confirmed: bool


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    id_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


@dataclass(frozen=True)
class AuthChallenge:
    name: str
    session: str
    parameters: dict[str, str]


AuthOutcome = AuthTokens | AuthChallenge


class CognitoGateway:
    """Envuelve el cliente boto3; el cliente se crea en la primera llamada."""

    def __init__(self, client_id: str, client_factory: Callable[[], Any], user_pool_id: str = "") -> None:
        self._client_id = client_id
        self._user_pool_id = user_pool_id
        self._client_factory = client_factory
        self._client: Any = None
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._client_factory()
        return self._client

    # -- operaciones -------------------------------------------------------

    def sign_up(self, email: str, password: str, full_name: str, dpi: str) -> SignUpResult:
        response = self._call(
            SIGN_UP,
            "sign_up",
            ClientId=self._client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": full_name},
                {"Name": "custom:dpi", "Value": dpi},
            ],
        )
        return SignUpResult(sub=str(response["UserSub"]), confirmed=bool(response.get("UserConfirmed")))

    def confirm_sign_up(self, email: str, code: str) -> None:
        self._call(CONFIRM_SIGN_UP, "confirm_sign_up", ClientId=self._client_id, Username=email, ConfirmationCode=code)

    def resend_confirmation_code(self, email: str) -> None:
        self._call(RESEND_CODE, "resend_confirmation_code", ClientId=self._client_id, Username=email)

    def password_auth(self, email: str, password: str, *, reauthentication: bool = False) -> AuthOutcome:
        operation = REAUTHENTICATE if reauthentication else LOGIN
        response = self._call(
            operation,
            "initiate_auth",
            ClientId=self._client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        return self._outcome(operation, response)

    def initiate_custom_auth(self, email: str) -> AuthOutcome:
        """Inicia el reto facial (CUSTOM_AUTH, cliente público: sin SecretHash ni IAM)."""
        response = self._call(
            FACE_INITIATE,
            "initiate_auth",
            ClientId=self._client_id,
            AuthFlow="CUSTOM_AUTH",
            AuthParameters={"USERNAME": email},
        )
        return self._outcome(FACE_INITIATE, response)

    def respond_to_custom_challenge(self, *, username: str, session: str, answer: str) -> AuthOutcome:
        """Responde el reto facial. ``answer`` es el JSON que espera VerifyAuthChallengeResponse."""
        response = self._call(
            FACE_RESPOND,
            "respond_to_auth_challenge",
            ClientId=self._client_id,
            ChallengeName="CUSTOM_CHALLENGE",
            Session=session,
            ChallengeResponses={"USERNAME": username, "ANSWER": answer},
        )
        return self._outcome(FACE_RESPOND, response)

    def _outcome(self, operation: str, response: dict[str, Any]) -> AuthOutcome:
        result = response.get("AuthenticationResult")
        if result:
            try:
                return AuthTokens(
                    access_token=result["AccessToken"],
                    id_token=result["IdToken"],
                    refresh_token=result["RefreshToken"],
                    expires_in=int(result["ExpiresIn"]),
                )
            except (KeyError, TypeError, ValueError):
                self._log(operation, 0.0, error_type="IncompleteAuthenticationResult")
                raise ServiceUnavailableError() from None
        challenge = response.get("ChallengeName")
        if challenge and response.get("Session"):
            parameters = {str(k): str(v) for k, v in (response.get("ChallengeParameters") or {}).items()}
            return AuthChallenge(name=str(challenge), session=str(response["Session"]), parameters=parameters)
        self._log(operation, 0.0, error_type="UnexpectedAuthResponse")
        raise ServiceUnavailableError()

    def update_attributes(self, access_token: str, *, full_name: str | None = None, dpi: str | None = None) -> None:
        attributes = []
        if full_name is not None:
            attributes.append({"Name": "name", "Value": full_name})
        if dpi is not None:
            attributes.append({"Name": "custom:dpi", "Value": dpi})
        if attributes:
            self._call(UPDATE_ATTRIBUTES, "update_user_attributes", AccessToken=access_token, UserAttributes=attributes)

    def update_face_reference(self, sub: str, reference_key: str) -> None:
        """Escribe custom:face_reference_key con las credenciales del rol (operación de administración)."""
        if not self._user_pool_id:
            raise ServiceUnavailableError()
        self._call(
            UPDATE_FACE_REFERENCE,
            "admin_update_user_attributes",
            UserPoolId=self._user_pool_id,
            Username=sub,
            UserAttributes=[{"Name": FACE_REFERENCE_ATTRIBUTE, "Value": reference_key}],
        )

    def get_user_attributes(self, access_token: str) -> dict[str, str]:
        response = self._call(GET_USER, "get_user", AccessToken=access_token)
        return {str(a["Name"]): str(a.get("Value", "")) for a in response.get("UserAttributes", [])}

    # -- infraestructura ---------------------------------------------------

    def _call(self, operation: str, method: str, **kwargs: Any) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            response = getattr(self._get_client(), method)(**kwargs)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "Unknown")
            if (
                operation == FACE_INITIATE
                and code == "UserLambdaValidationException"
                and _MISSING_REFERENCE_MARKER in str(error.get("Message", ""))
            ):
                code = _MISSING_REFERENCE_CODE
            raise self._map_error(operation, code, start, type(exc).__name__) from None
        except BotoCoreError as exc:
            # Sin red, timeout, DNS o región inválida.
            self._log(operation, start, error_type=type(exc).__name__)
            raise ServiceUnavailableError() from None
        self._log(operation, start)
        return response

    def _map_error(self, operation: str, code: str, start: float, exception_name: str) -> ApiError:
        rule = _RULES.get(operation, {}).get(code)
        if rule is not None:
            status, api_code, message, reason = rule
            self._log(operation, start, error_type=exception_name, aws_error_code=code, level=logging.INFO)
            return ApiError(status, api_code, message, details={"reason": reason} if reason else None)
        if code in _RATE_LIMITED:
            self._log(operation, start, error_type=exception_name, aws_error_code=code)
            return ApiError(429, "RATE_LIMITED")
        # Configuración (pool o cliente inexistente, flujo no habilitado, Lambda,
        # WAF, plan) o falla de Cognito: nada que el usuario pueda corregir.
        self._log(operation, start, error_type=exception_name, aws_error_code=code, level=logging.ERROR)
        return ServiceUnavailableError()

    @staticmethod
    def _log(
        operation: str,
        start: float,
        *,
        error_type: str | None = None,
        aws_error_code: str | None = None,
        level: int | None = None,
    ) -> None:
        extra: dict[str, Any] = {
            "event": "cognito.call",
            "operation": operation,
            "durationMs": round((time.perf_counter() - start) * 1000, 1) if start else 0.0,
        }
        if error_type:
            extra["errorType"] = error_type
        if aws_error_code:
            extra["awsErrorCode"] = aws_error_code
        if level is None:
            level = logging.WARNING if error_type else logging.INFO
        logger.log(level, "cognito", extra=extra)
