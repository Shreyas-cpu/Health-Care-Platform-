from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.appointment import AppointmentRead
from backend.app.schemas.booking import (
    BookingConfirmRequest,
    BookingReserveRequest,
    BookingReserveResponse,
)
from backend.app.services.booking_service import confirm_booking, reserve_slot

router = APIRouter(prefix="/bookings", tags=["Atomic Booking"])


@router.post(
    "/reserve",
    response_model=BookingReserveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reserve_booking(
    req: BookingReserveRequest,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Authenticated patient reserves a slot with Redis lock + pending payment order."""
    return await reserve_slot(current_user.id, req, session)


@router.post("/confirm", response_model=AppointmentRead)
async def confirm_booking_endpoint(
    req: BookingConfirmRequest,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Patient submits payment verification to atomically confirm booking."""
    appt = await confirm_booking(req, session)
    return appt
