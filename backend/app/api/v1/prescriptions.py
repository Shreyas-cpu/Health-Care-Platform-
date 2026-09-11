import uuid

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.chemist import PrescriptionVerificationResponse
from backend.app.schemas.prescription import (
    DrugMasterResponse,
    PrescriptionCreate,
    PrescriptionResponse,
)
from backend.app.services.prescription_service import (
    create_prescription,
    get_prescription,
    search_drugs,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


@router.post(
    "", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED
)
async def create_prescription_endpoint(
    req: PrescriptionCreate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Doctor creates a prescription with CMP-01 telemedicine restriction checks."""
    return await create_prescription(current_user.id, req, session)


@router.get("/drugs/autocomplete", response_model=list[DrugMasterResponse])
async def drug_autocomplete(
    query: str = Query(..., min_length=1),
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Search DrugMaster for medication autocomplete."""
    return await search_drugs(query, session)


@router.get("/{prescription_id}", response_model=PrescriptionResponse)
async def get_prescription_endpoint(
    prescription_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Return prescription details including a pre-signed download URL."""
    if current_user.role == UserRole.PATIENT:
        return await get_prescription(
            prescription_id,
            session,
            requester_id=current_user.id,
            require_patient=True,
        )
    return await get_prescription(
        prescription_id,
        session,
        requester_id=current_user.id,
        require_doctor=True,
    )


@router.get(
    "/{prescription_id}/verify", response_model=PrescriptionVerificationResponse
)
async def verify_prescription_endpoint(
    prescription_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Verify digital signature and integrity of any prescription."""
    from backend.app.api.v1.chemists import verify_prescription_signature_endpoint

    return await verify_prescription_signature_endpoint(prescription_id, session)
