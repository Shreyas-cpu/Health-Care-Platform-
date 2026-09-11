import uuid

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.prescription import PrescriptionResponse
from backend.app.services.prescription_service import (
    get_patient_prescription_download_url,
    list_patient_prescriptions,
)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/patient/records", tags=["Patient Health Records"])


@router.get("/prescriptions", response_model=list[PrescriptionResponse])
async def list_my_prescriptions(
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Patient views all prescriptions from completed visits."""
    return await list_patient_prescriptions(current_user.id, session)


@router.get("/prescriptions/{prescription_id}/download")
async def download_my_prescription(
    prescription_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Patient downloads a pre-signed URL for a prescription PDF."""
    return await get_patient_prescription_download_url(
        prescription_id,
        current_user.id,
        session,
    )
