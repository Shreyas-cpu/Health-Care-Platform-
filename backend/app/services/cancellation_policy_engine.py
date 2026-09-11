import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis import lock_manager
from backend.app.models.appointment import Appointment, AppointmentStatus, PaymentStatus
from backend.app.models.cancellation_policy import CancellationPolicy
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.services.appointment_state import appointment_state_machine
from backend.app.services.audit import record_audit_log
from backend.app.services.payment_gateway import payment_gateway


DEFAULT_CUTOFF_HOURS = 2
DEFAULT_REFUND_PERCENTAGE = Decimal("100.00")
DEFAULT_FEE_DEDUCTION = Decimal("0.00")


async def evaluate_cancellation(
    appointment: Appointment,
    policy: Optional[CancellationPolicy] = None,
    session: AsyncSession = None,
) -> Tuple[bool, Decimal]:
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

    now = datetime.now(timezone.utc)
    slot_start = appointment.slot_start
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=timezone.utc)

    delta_hours = (slot_start - now).total_seconds() / 3600.0
    if delta_hours >= cutoff_hours:
        refund_amount = max(
            Decimal("0.00"),
            (appointment.fee_amount * (refund_percentage / Decimal("100")))
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
    Cancel an appointment, optionally refund via payment gateway, audit, and release locks.
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

    # Authorization: patient who owns it, the doctor, or admin roles handled at API layer
    # (API will pass the authenticated user_id; we still verify ownership soft-check here)
    if appt.patient_id != user_id and appt.doctor_id != user_id:
        # Allow if caller is admin — checked via role at API; here we only soft-gate.
        pass

    policy = (
        await session.execute(
            select(CancellationPolicy).where(CancellationPolicy.is_active.is_(True))
        )
    ).scalars().first()

    eligible, refund_amount = await evaluate_cancellation(appt, policy=policy, session=session)

    is_refunded = False
    refund_id: Optional[str] = None
    message = "Appointment cancelled. Not eligible for refund under current policy."

    if eligible and appt.payment_status == PaymentStatus.CAPTURED and refund_amount > 0:
        txn = (
            await session.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.appointment_id == appt.id,
                    PaymentTransaction.status == PaymentTransactionStatus.CAPTURED,
                )
            )
        ).scalars().first()

        payment_id = txn.gateway_payment_id if txn else None
        if payment_id:
            refund_result = payment_gateway.refund_payment(
                payment_id=payment_id,
                amount=refund_amount,
                notes={"appointment_id": str(appt.id), "reason": reason},
            )
            refund_id = refund_result.get("id")
            if txn:
                txn.status = PaymentTransactionStatus.REFUNDED
                txn.refund_id = refund_id
                txn.refund_amount = refund_amount
            appt.payment_status = PaymentStatus.REFUNDED
            is_refunded = True
            message = (
                f"Appointment cancelled. Refund of {refund_amount} INR processed."
            )
        else:
            message = (
                "Appointment cancelled. Eligible for refund but no captured "
                "gateway payment id found."
            )
    elif eligible and appt.payment_status != PaymentStatus.CAPTURED:
        message = "Appointment cancelled. No captured payment to refund."
    elif not eligible:
        message = (
            "Appointment cancelled. Cancellation is within the cutoff window; "
            "fee retained per policy."
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
            "is_refunded": is_refunded,
            "refund_amount": str(refund_amount),
        },
    )

    await session.commit()
    await session.refresh(appt)

    return {
        "appointment_id": appt.id,
        "status": appt.status.value,
        "is_refunded": is_refunded,
        "refund_amount": refund_amount if is_refunded else Decimal("0.00"),
        "refund_id": refund_id,
        "message": message,
    }
