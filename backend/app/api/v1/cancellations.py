import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.appointment import Appointment
from backend.app.models.user import User, UserRole
from backend.app.schemas.cancellation import CancellationRequest, CancellationResponse
from backend.app.services.cancellation_policy_engine import process_cancellation
from sqlalchemy import select

router = APIRouter(prefix="/appointments", tags=["Cancellations"])


@router.post("/{appointment_id}/cancel", response_model=CancellationResponse)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    req: CancellationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Authenticated user cancels an appointment with a mandatory reason."""
    appt = (
        await session.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
    ).scalar_one_or_none()
    if appt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    is_owner = appt.patient_id == current_user.id or appt.doctor_id == current_user.id
    is_admin = current_user.role in {
        UserRole.SUPER_ADMIN,
        UserRole.VERIFICATION_REVIEWER,
    }
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this appointment",
        )

    result = await process_cancellation(
        appointment_id=appointment_id,
        reason=req.reason,
        user_id=current_user.id,
        session=session,
    )
    return CancellationResponse(**result)
