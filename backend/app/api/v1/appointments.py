import uuid

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.appointment import AppointmentRead
from backend.app.services.booking_service import confirm_appointment
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("/{appointment_id}/confirm", response_model=AppointmentRead)
async def confirm_appointment_endpoint(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Doctor or clinic confirms the appointment (REQUESTED -> CONFIRMED)."""
    return await confirm_appointment(
        appointment_id=appointment_id,
        doctor_user_id=current_user.id,
        session=session,
    )
