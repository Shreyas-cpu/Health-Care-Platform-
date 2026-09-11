import uuid

from backend.app.core.redis import lock_manager
from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.doctor import Doctor
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.schemas.booking import (
    BookingConfirmRequest,
    BookingReserveRequest,
    BookingReserveResponse,
)
from backend.app.services.appointment_state import appointment_state_machine
from backend.app.services.payment_gateway import payment_gateway
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

SLOT_LOCK_TTL_SECONDS = 600


async def reserve_slot(
    patient_id: uuid.UUID,
    req: BookingReserveRequest,
    session: AsyncSession,
) -> BookingReserveResponse:
    """
    Atomically reserve a doctor slot with Redis lock + PostgreSQL appointment insert.
    Creates a pending gateway order and PaymentTransaction.
    """
    slot_iso = req.slot_start.isoformat()
    lock_token = await lock_manager.acquire_slot_lock(
        str(req.doctor_id), slot_iso, ttl_seconds=SLOT_LOCK_TTL_SECONDS
    )
    if lock_token is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot is currently being booked by another patient",
        )

    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == req.doctor_id))
    ).scalar_one_or_none()
    if doctor is None:
        await lock_manager.release_slot_lock(str(req.doctor_id), slot_iso, lock_token)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    if req.mode == AppointmentMode.VIDEO:
        fee_amount = doctor.video_fee
    else:
        fee_amount = doctor.in_person_fee

    appointment = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=req.doctor_id,
        clinic_id=req.clinic_id,
        mode=req.mode,
        status=AppointmentStatus.REQUESTED,
        slot_start=req.slot_start,
        slot_end=req.slot_end,
        fee_amount=fee_amount,
        payment_status=PaymentStatus.PENDING,
        lock_token=lock_token,
    )
    session.add(appointment)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        await lock_manager.release_slot_lock(str(req.doctor_id), slot_iso, lock_token)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot has already been booked",
        ) from None

    order = payment_gateway.create_order(
        amount=fee_amount,
        currency="INR",
        receipt=f"appt_{appointment.id.hex[:12]}",
    )
    payment_txn = PaymentTransaction(
        id=uuid.uuid4(),
        appointment_id=appointment.id,
        gateway_order_id=order["id"],
        amount=fee_amount,
        currency="INR",
        status=PaymentTransactionStatus.PENDING,
    )
    session.add(payment_txn)
    await session.commit()
    await session.refresh(appointment)

    return BookingReserveResponse(
        appointment_id=appointment.id,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.patient_id,
        slot_start=appointment.slot_start,
        slot_end=appointment.slot_end,
        mode=appointment.mode,
        fee_amount=appointment.fee_amount,
        status=appointment.status,
        payment_status=appointment.payment_status,
        lock_token=lock_token,
        order_id=order["id"],
    )


async def confirm_booking(
    req: BookingConfirmRequest,
    session: AsyncSession,
) -> Appointment:
    """
    Verify payment signature and atomically capture payment + confirm appointment.
    Releases the Redis slot lock on success.
    """
    valid = payment_gateway.verify_payment_signature(
        razorpay_order_id=req.gateway_order_id,
        razorpay_payment_id=req.gateway_payment_id,
        razorpay_signature=req.gateway_signature,
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature",
        )

    appt = (
        await session.execute(
            select(Appointment).where(Appointment.id == req.appointment_id)
        )
    ).scalar_one_or_none()
    if appt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    txn = (
        await session.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.appointment_id == appt.id,
                PaymentTransaction.gateway_order_id == req.gateway_order_id,
            )
        )
    ).scalar_one_or_none()
    if txn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found for this appointment/order",
        )

    if txn.status == PaymentTransactionStatus.CAPTURED and appt.status == AppointmentStatus.CONFIRMED:
        return appt

    txn.status = PaymentTransactionStatus.CAPTURED
    txn.gateway_payment_id = req.gateway_payment_id

    if appt.status == AppointmentStatus.REQUESTED:
        await appointment_state_machine.transition(
            appt, AppointmentStatus.CONFIRMED, session
        )

    appt.payment_status = PaymentStatus.CAPTURED

    if appt.lock_token:
        await lock_manager.release_slot_lock(
            str(appt.doctor_id),
            appt.slot_start.isoformat(),
            appt.lock_token,
        )
        appt.lock_token = None

    await session.commit()
    await session.refresh(appt)
    return appt


async def create_payment_order_for_appointment(
    appointment_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """Create (or return existing) gateway order for an appointment."""
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

    existing = (
        await session.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.appointment_id == appointment_id,
                PaymentTransaction.status == PaymentTransactionStatus.PENDING,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "appointment_id": appointment_id,
            "order_id": existing.gateway_order_id,
            "amount": existing.amount,
            "currency": existing.currency,
            "key_id": payment_gateway.key_id,
        }

    order = payment_gateway.create_order(
        amount=appt.fee_amount,
        currency="INR",
        receipt=f"appt_{appt.id.hex[:12]}",
    )
    txn = PaymentTransaction(
        id=uuid.uuid4(),
        appointment_id=appt.id,
        gateway_order_id=order["id"],
        amount=appt.fee_amount,
        currency="INR",
        status=PaymentTransactionStatus.PENDING,
    )
    session.add(txn)
    await session.commit()
    return {
        "appointment_id": appointment_id,
        "order_id": order["id"],
        "amount": appt.fee_amount,
        "currency": "INR",
        "key_id": payment_gateway.key_id,
    }
