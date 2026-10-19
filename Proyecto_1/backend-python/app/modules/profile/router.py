"""Perfil propio (PRO-14).

- ``GET /me`` y ``POST /me/complete-profile`` exigen solo token válido: un
  perfil incompleto puede consultarse y completar la foto (contract.md).
- ``PATCH /me`` exige perfil completo (403 PROFILE_INCOMPLETE) y la contraseña
  actual. La identidad sale siempre del ``sub`` del token: no hay forma de
  editar a otro usuario.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.common.auth import Principal, get_access_token, get_current_principal, require_complete_profile
from app.common.contract import ContractModel, Dpi, Field, FullName
from app.modules.profile.service import ProfileService, ProfileUpdate

router = APIRouter(tags=["Perfil"], dependencies=[Depends(get_current_principal)])


class UpdateProfileRequest(ContractModel):
    fullName: FullName | None = None
    dpi: Dpi | None = None
    profileImageKey: str | None = Field(default=None, min_length=1)
    currentPassword: str = Field(min_length=1)


class CompleteProfileRequest(ContractModel):
    profileImageKey: str = Field(min_length=1)


def get_profile_service(request: Request) -> ProfileService:
    return request.app.state.profile_service


@router.get("/me", operation_id="getMyProfile")
def get_my_profile(
    principal: Principal = Depends(get_current_principal),
    access_token: str = Depends(get_access_token),
    service: ProfileService = Depends(get_profile_service),
) -> dict:
    return service.get(principal, access_token)


@router.patch("/me", operation_id="updateMyProfile")
def update_my_profile(
    body: UpdateProfileRequest,
    principal: Principal = Depends(require_complete_profile),
    service: ProfileService = Depends(get_profile_service),
) -> dict:
    change = ProfileUpdate(
        current_password=body.currentPassword,
        full_name=body.fullName,
        dpi=body.dpi,
        profile_image_key=body.profileImageKey,
    )
    return service.update(principal, change)


@router.post("/me/complete-profile", operation_id="completeMyProfile")
def complete_my_profile(
    body: CompleteProfileRequest,
    principal: Principal = Depends(get_current_principal),
    access_token: str = Depends(get_access_token),
    service: ProfileService = Depends(get_profile_service),
) -> dict:
    return service.complete(principal, access_token, body.profileImageKey)
