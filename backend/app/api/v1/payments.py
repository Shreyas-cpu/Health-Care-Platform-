from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.appointment import AppointmentRead
from backend.app.schemas.booking import (
    BookingConfirmRequest,
    PaymentCreateOrderRequest,
    PaymentCreateOrderResponse,
    PaymentVerifyRequest,
)
from backend.app.services.booking_service import (
    confirm_booking,
    create_payment_order_for_appointment,
)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/create-order", response_model=PaymentCreateOrderResponse)
async def create_order(
    req: PaymentCreateOrderRequest,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Initiate gateway order for an appointment fee."""
    result = await create_payment_order_for_appointment(req.appointment_id, session)
    return PaymentCreateOrderResponse(**result)


@router.post("/verify-and-capture", response_model=AppointmentRead)
async def verify_and_capture(
    req: PaymentVerifyRequest,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """
    Atomic capture: update PaymentTransaction to CAPTURED, confirm appointment,
    and release Redis slot lock.
    """
    confirm_req = BookingConfirmRequest(
        appointment_id=req.appointment_id,
        gateway_order_id=req.gateway_order_id,
        gateway_payment_id=req.gateway_payment_id,
        gateway_signature=req.gateway_signature,
    )
    return await confirm_booking(confirm_req, session)
