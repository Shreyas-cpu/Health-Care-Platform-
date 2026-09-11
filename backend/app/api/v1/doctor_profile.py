import uuid

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.search import (
    ClinicCreateOrUpdate,
    ClinicRead,
    DoctorPublicProfile,
    ToggleListingRequest,
    ToggleVideoRequest,
)
from backend.app.services.catalog import (
    get_public_doctor_profile,
    toggle_doctor_listing,
    toggle_doctor_video,
    upsert_doctor_clinic,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/doctors", tags=["Doctor Public Profile & Practice"])


@router.post("/me/clinic", response_model=ClinicRead)
async def save_clinic(
    data: ClinicCreateOrUpdate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    return await upsert_doctor_clinic(session, current_user.id, data)


@router.post("/me/toggle-listing")
async def toggle_listing(
    data: ToggleListingRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await toggle_doctor_listing(
            session, current_user.id, data.listing_online
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/me/toggle-video")
async def toggle_video(
    data: ToggleVideoRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await toggle_doctor_video(session, current_user.id, data.video_enabled)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/{doctor_id}", response_model=DoctorPublicProfile)
async def public_profile(doctor_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    profile = await get_public_doctor_profile(session, doctor_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found."
        )
    return profile
