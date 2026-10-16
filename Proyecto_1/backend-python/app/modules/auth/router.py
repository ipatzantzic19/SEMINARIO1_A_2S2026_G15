"""Autenticación pública (Cognito). Pendiente: PRO-14 (login facial con PRO-31).

Las rutas ya validan el cuerpo según el contrato (400 VALIDATION_ERROR) y
responden 501 NOT_IMPLEMENTED hasta implementar el flujo con Cognito.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from app.common.contract import ContractModel, Dpi, Email, Field, FullName
from app.common.errors import NotImplementedApiError

TICKET = "PRO-14"
router = APIRouter(prefix="/auth", tags=["Autenticación"])


class RegisterRequest(ContractModel):
    fullName: FullName
    email: Email
    dpi: Dpi
    password: str = Field(min_length=8)


class ConfirmRequest(ContractModel):
    email: Email
    code: str = Field(min_length=6, max_length=8)


class LoginRequest(ContractModel):
    email: Email
    password: str = Field(min_length=8)


class FaceChallengeRequest(ContractModel):
    email: Email


class FaceVerifyRequest(ContractModel):
    captureKey: str


@router.post("/register", operation_id="register", status_code=201)
def register(body: RegisterRequest) -> None:
    raise NotImplementedApiError(TICKET, "register")


@router.post("/confirm", operation_id="confirmRegistration", status_code=204)
def confirm_registration(body: ConfirmRequest) -> None:
    raise NotImplementedApiError(TICKET, "confirmRegistration")


@router.post("/login", operation_id="login")
def login(body: LoginRequest) -> None:
    raise NotImplementedApiError(TICKET, "login")


@router.post("/face/challenges", operation_id="createFaceChallenge", status_code=201)
def create_face_challenge(body: FaceChallengeRequest) -> None:
    raise NotImplementedApiError(TICKET, "createFaceChallenge")


@router.post("/face/challenges/{challengeId}/verify", operation_id="verifyFaceChallenge")
def verify_face_challenge(challengeId: Annotated[UUID, Path()], body: FaceVerifyRequest) -> None:
    raise NotImplementedApiError(TICKET, "verifyFaceChallenge")
