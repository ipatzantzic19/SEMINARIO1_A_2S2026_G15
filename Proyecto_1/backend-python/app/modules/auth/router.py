"""Autenticación pública con Cognito (PRO-14).

- ``register``, ``confirm`` y ``login`` son adaptadores hacia el mismo User Pool
  que usa Node; payloads, errores y decisiones en docs/api/python-auth.md.
- Login facial (``/auth/face/*``): fuera de alcance. Valida el cuerpo (400) y
  responde 501 NOT_IMPLEMENTED; estado y opciones en python-auth.md §8.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import JSONResponse

from app.common.contract import ContractModel, Dpi, Email, Field, FullName, Password, PlainText
from app.common.errors import NotImplementedApiError
from app.modules.auth.service import AuthService

# El login facial depende del diseño de PRO-31 (triggers, prefijos, sesión).
FACE_TICKET = "PRO-31"
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


class LoginRequest(ContractModel):
    email: Email
    password: Password = Field(min_length=8)


class FaceChallengeRequest(ContractModel):
    email: Email


class FaceVerifyRequest(ContractModel):
    captureKey: str


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


@router.post("/register", operation_id="register", status_code=201)
def register(body: RegisterRequest, service: AuthService = Depends(get_auth_service)) -> dict:
    return service.register(email=body.email, password=body.password, full_name=body.fullName, dpi=body.dpi)


@router.post("/confirm", operation_id="confirmRegistration", status_code=204)
def confirm_registration(body: ConfirmRequest, service: AuthService = Depends(get_auth_service)) -> Response:
    service.confirm(email=body.email, code=body.code)
    return Response(status_code=204)


@router.post("/login", operation_id="login")
def login(body: LoginRequest, service: AuthService = Depends(get_auth_service)) -> JSONResponse:
    status, payload = service.login(email=body.email, password=body.password)
    return JSONResponse(status_code=status, content=payload)


@router.post("/face/challenges", operation_id="createFaceChallenge", status_code=201)
def create_face_challenge(body: FaceChallengeRequest) -> None:
    raise NotImplementedApiError(FACE_TICKET, "createFaceChallenge")


@router.post("/face/challenges/{challengeId}/verify", operation_id="verifyFaceChallenge")
def verify_face_challenge(challengeId: Annotated[UUID, Path()], body: FaceVerifyRequest) -> None:
    raise NotImplementedApiError(FACE_TICKET, "verifyFaceChallenge")
