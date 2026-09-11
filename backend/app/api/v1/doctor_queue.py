import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.appointment import AppointmentRead
from backend.app.schemas.queue import QueueAppointmentResponse
from backend.app.services.queue_service import (
    get_doctor_daily_queue,
    mark_appointment_complete,
    mark_appointment_no_show,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/doctor/queue", tags=["Doctor Clinical Queue"])


@router.get("", response_model=list[QueueAppointmentResponse])
async def doctor_daily_queue(
    queue_date: date | None = Query(default=None, alias="date"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Doctor gets their daily clinical queue (defaults to today IST)."""
    target = queue_date or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    return await get_doctor_daily_queue(current_user.id, target, session)


@router.post("/{appointment_id}/mark-complete", response_model=AppointmentRead)
async def queue_mark_complete(
    appointment_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    return await mark_appointment_complete(appointment_id, current_user.id, session)


@router.post("/{appointment_id}/mark-no-show", response_model=AppointmentRead)
async def queue_mark_no_show(
    appointment_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    return await mark_appointment_no_show(appointment_id, current_user.id, session)
