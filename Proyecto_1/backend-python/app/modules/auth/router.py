"""Autenticación pública con Cognito (PRO-14).

- ``register``, ``confirm``, ``confirm/resend`` y ``login`` son adaptadores hacia el mismo User Pool
  que usa Node; payloads, errores y decisiones en docs/api/python-auth.md.
- Login facial (``/auth/face/*``): Cognito CUSTOM_AUTH con la Session en memoria
  (docs/api/python-face-login.md). Los tokens los emite Cognito; Python no crea sesión propia.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import JSONResponse

from app.common.contract import ContractModel, Dpi, Email, Field, FullName, Password, PlainText
from app.modules.auth.face import FaceLoginService
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class RegisterRequest(ContractModel):
    fullName: FullName
    email: Email
    dpi: Dpi
    # openapi.yaml exige minLength 8; la política completa del pool (12 y
    # complejidad) se valida en el servicio para responder un mensaje claro.
    password: Password = Field(min_length=8)


class ConfirmRequest(ContractModel):
    email: Email
    code: PlainText = Field(min_length=6, max_length=8)


class ResendRequest(ContractModel):
    email: Email


class LoginRequest(ContractModel):
    email: Email
    password: Password = Field(min_length=8)


class FaceChallengeRequest(ContractModel):
    email: Email


class FaceVerifyRequest(ContractModel):
    captureKey: str = Field(min_length=1, max_length=1024)


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_face_service(request: Request) -> FaceLoginService:
    return request.app.state.face_service


@router.post("/register", operation_id="register", status_code=201)
def register(body: RegisterRequest, service: AuthService = Depends(get_auth_service)) -> dict:
    return service.register(email=body.email, password=body.password, full_name=body.fullName, dpi=body.dpi)


@router.post("/confirm", operation_id="confirmRegistration", status_code=204)
def confirm_registration(body: ConfirmRequest, service: AuthService = Depends(get_auth_service)) -> Response:
    service.confirm(email=body.email, code=body.code)
    return Response(status_code=204)


@router.post("/confirm/resend", operation_id="resendConfirmationCode", status_code=204)
def resend_confirmation_code(body: ResendRequest, service: AuthService = Depends(get_auth_service)) -> Response:
    service.resend_confirmation(email=body.email)
    return Response(status_code=204)


@router.post("/login", operation_id="login")
def login(body: LoginRequest, service: AuthService = Depends(get_auth_service)) -> JSONResponse:
    status, payload = service.login(email=body.email, password=body.password)
    return JSONResponse(status_code=status, content=payload)


@router.post("/face/challenges", operation_id="createFaceChallenge", status_code=201)
def create_face_challenge(body: FaceChallengeRequest, service: FaceLoginService = Depends(get_face_service)) -> dict:
    return service.create_challenge(email=body.email)


@router.post("/face/challenges/{challengeId}/verify", operation_id="verifyFaceChallenge")
def verify_face_challenge(
    challengeId: Annotated[UUID, Path()],
    body: FaceVerifyRequest,
    service: FaceLoginService = Depends(get_face_service),
) -> dict:
    return service.verify(challenge_id=str(challengeId), capture_key=body.captureKey)
