import uuid

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.verification import (
    DoctorDocumentRead,
    VerificationQueueItemRead,
    VerificationTransitionRequest,
)
from backend.app.services.verification_state import verification_state_machine
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/admin/verification", tags=["Admin Doctor Verification Pipeline"])

@router.get("/queue", response_model=list[VerificationQueueItemRead])
async def get_verification_queue(
    filter_status: VerificationStatus | None = None,
    current_admin: User = Depends(require_roles(UserRole.VERIFICATION_REVIEWER, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves doctors in the verification queue.
    By default returns 'submitted', 'under_review', and 'info_requested'.
    """
    stmt = select(Doctor).options(selectinload(Doctor.documents))
    if filter_status:
        stmt = stmt.where(Doctor.verification_status == filter_status)
    else:
        stmt = stmt.where(Doctor.verification_status.in_([
            VerificationStatus.SUBMITTED,
            VerificationStatus.UNDER_REVIEW,
            VerificationStatus.INFO_REQUESTED
        ]))
    
    stmt = stmt.order_by(Doctor.created_at.asc())
    results = (await session.execute(stmt)).scalars().all()

    queue_items = []
    for doc in results:
        # Provide presigned download URLs for reviewers to inspect documents securely
        docs_read = []
        for d in doc.documents:
            docs_read.append(DoctorDocumentRead.model_validate(d))
        queue_items.append(VerificationQueueItemRead(doctor=doc, documents=docs_read))

    return queue_items

@router.get("/{doctor_id}", response_model=VerificationQueueItemRead)
async def get_doctor_verification_details(
    doctor_id: uuid.UUID,
    current_admin: User = Depends(require_roles(UserRole.VERIFICATION_REVIEWER, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Doctor)
        .options(selectinload(Doctor.documents))
        .where(Doctor.user_id == doctor_id)
    )
    doctor = (await session.execute(stmt)).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")

    docs_read = [DoctorDocumentRead.model_validate(d) for d in doctor.documents]
    return VerificationQueueItemRead(doctor=doctor, documents=docs_read)

@router.post("/{doctor_id}/transition", response_model=VerificationQueueItemRead)
async def transition_verification_status(
    doctor_id: uuid.UUID,
    req: VerificationTransitionRequest,
    request: Request,
    current_admin: User = Depends(require_roles(UserRole.VERIFICATION_REVIEWER, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db)
):
    """
    Transitions doctor verification status through the 6-state pipeline.
    Mandates reason for rejections and suspensions.
    Writes immutable audit log entry in the same transaction (RUL-04).
    """
    stmt = (
        select(Doctor)
        .options(selectinload(Doctor.documents))
        .where(Doctor.user_id == doctor_id)
    )
    doctor = (await session.execute(stmt)).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")

    client_ip = request.client.host if request.client else None

    # Execute transition
    await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=req.new_status,
        admin_user_id=current_admin.id,
        session=session,
        reason_text=req.reason_text,
        review_notes=req.review_notes,
        ip_address=client_ip
    )

    await session.commit()
    await session.refresh(doctor)

    docs_read = [DoctorDocumentRead.model_validate(d) for d in doctor.documents]
    return VerificationQueueItemRead(doctor=doctor, documents=docs_read)
