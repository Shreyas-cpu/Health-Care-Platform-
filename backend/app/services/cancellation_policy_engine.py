import uuid
from datetime import UTC, datetime
from decimal import Decimal

from backend.app.core.redis import lock_manager
from backend.app.models.appointment import Appointment, AppointmentStatus, PaymentStatus
from backend.app.models.cancellation_policy import CancellationPolicy
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.services.appointment_state import appointment_state_machine
from backend.app.services.audit import record_audit_log
from backend.app.services.payment_gateway import payment_gateway
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_CUTOFF_HOURS = 2
DEFAULT_REFUND_PERCENTAGE = Decimal("100.00")
DEFAULT_FEE_DEDUCTION = Decimal("0.00")


async def evaluate_cancellation(
    appointment: Appointment,
    policy: CancellationPolicy | None = None,
    session: AsyncSession = None,
) -> tuple[bool, Decimal]:
    """
    Determine refund eligibility based on cutoff hours before slot_start.

    Returns (is_eligible, refund_amount).
    """
    if policy is None and session is not None:
        policy = (
            await session.execute(
                select(CancellationPolicy).where(CancellationPolicy.is_active.is_(True))
            )
        ).scalars().first()

    cutoff_hours = policy.cutoff_hours if policy else DEFAULT_CUTOFF_HOURS
    refund_percentage = (
        policy.refund_percentage if policy else DEFAULT_REFUND_PERCENTAGE
    )
    fee_deduction = policy.fee_deduction if policy else DEFAULT_FEE_DEDUCTION

    now = datetime.now(UTC)
    slot_start = appointment.slot_start
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=UTC)

    delta_hours = (slot_start - now).total_seconds() / 3600.0
    if delta_hours >= cutoff_hours:
        refund_amount = max(
            Decimal("0.00"),
            (appointment.fee_amount * (refund_percentage / Decimal(100)))
            - fee_deduction,
        )
        return True, refund_amount.quantize(Decimal("0.01"))

    return False, Decimal("0.00")


async def process_cancellation(
    appointment_id: uuid.UUID,
    reason: str,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """
    Cancel an appointment purely without payment gateway refund calculations,
    audit the event, and release Redis slot locks.
    Cancelled appointments drop out of the exclusion constraint inventory filter.
    """
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

    if appt.status in {AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment in status '{appt.status.value}' cannot be cancelled",
        )

    await appointment_state_machine.transition(
        appt,
        AppointmentStatus.CANCELLED,
        session,
        reason=reason,
    )

    if appt.lock_token:
        try:
            await lock_manager.release_slot_lock(
                str(appt.doctor_id),
                appt.slot_start.isoformat(),
                appt.lock_token,
            )
        except Exception:
            pass
        appt.lock_token = None

    await record_audit_log(
        admin_user_id=user_id,
        target_entity_type="appointment",
        target_entity_id=appt.id,
        action="cancel_appointment",
        reason=reason,
        session=session,
        previous_state={"status": "pre_cancel"},
        new_state={
            "status": AppointmentStatus.CANCELLED.value,
            "is_refunded": False,
            "refund_amount": "0.00",
        },
    )

    await session.commit()
    await session.refresh(appt)

    return {
        "appointment_id": appt.id,
        "status": appt.status.value,
        "is_refunded": False,
        "refund_amount": Decimal("0.00"),
        "refund_id": None,
        "message": "Appointment cancelled successfully.",
    }
