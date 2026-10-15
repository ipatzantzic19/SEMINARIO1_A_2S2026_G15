"""Perfil propio. Pendiente: PRO-14.

Requiere access token válido pero NO perfil completo: un perfil incompleto
solo puede consultar ``/me`` y completar la foto (contract.md).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.common.auth import get_current_principal
from app.common.contract import ContractModel, Dpi, Field, FullName
from app.common.errors import NotImplementedApiError

TICKET = "PRO-14"
router = APIRouter(tags=["Perfil"], dependencies=[Depends(get_current_principal)])


class UpdateProfileRequest(ContractModel):
    fullName: FullName | None = None
    dpi: Dpi | None = None
    profileImageKey: str | None = None
    currentPassword: str


class CompleteProfileRequest(ContractModel):
    profileImageKey: str = Field(min_length=1)


@router.get("/me", operation_id="getMyProfile")
def get_my_profile() -> None:
    raise NotImplementedApiError(TICKET, "getMyProfile")


@router.patch("/me", operation_id="updateMyProfile")
def update_my_profile(body: UpdateProfileRequest) -> None:
    raise NotImplementedApiError(TICKET, "updateMyProfile")


@router.post("/me/complete-profile", operation_id="completeMyProfile")
def complete_my_profile(body: CompleteProfileRequest) -> None:
    raise NotImplementedApiError(TICKET, "completeMyProfile")
