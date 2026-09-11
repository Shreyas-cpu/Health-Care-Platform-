import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.cancellation_policy import CancellationPolicy
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.models.schedule import DoctorAvailability
from backend.app.models.user import User, UserRole
from backend.app.schemas.booking import BookingConfirmRequest, BookingReserveRequest
from backend.app.services.booking_service import confirm_booking, reserve_slot
from backend.app.services.cancellation_policy_engine import (
    evaluate_cancellation,
    process_cancellation,
)
from backend.app.services.payment_gateway import payment_gateway
from backend.app.services.schedule_engine import generate_slots
from backend.tests.conftest import random_digits


async def _setup_confirmed_paid_appointment(
    session: AsyncSession,
    *,
    hours_until_slot: float,
    fee: Decimal = Decimal("500.00"),
) -> tuple[Appointment, Doctor, User]:
    patient = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{random_digits(8)}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    doctor_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{random_digits(8)}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    session.add_all([patient, doctor_user])
    await session.flush()

    doctor = Doctor(
        user_id=doctor_user.id,
        full_name="Dr. Cancel Tester",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Test Council",
        specialty="Cardiology",
        years_experience=8,
        in_person_fee=fee,
        video_fee=fee,
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
    )
    session.add(doctor)

    slot_start = datetime.now(timezone.utc) + timedelta(hours=hours_until_slot)
    # Align to the 30-minute grid used by full-day availability seeding
    # so cancelled slots reappear in generate_slots()
    slot_start = slot_start.replace(second=0, microsecond=0)
    aligned_minute = 0 if slot_start.minute < 30 else 30
    slot_start = slot_start.replace(minute=aligned_minute)
    slot_end = slot_start + timedelta(minutes=30)

    # Seed availability covering the slot weekday so rebooking inventory works
    availability = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=doctor_user.id,
        day_of_week=slot_start.date().weekday(),
        start_time=time(0, 0),
        end_time=time(23, 59),
        slot_duration_minutes=30,
        buffer_minutes=0,
        mode="in_person",
        is_active=True,
    )
    session.add(availability)

    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=doctor_user.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
        slot_start=slot_start,
        slot_end=slot_end,
        fee_amount=fee,
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add(appt)
    await session.flush()

    txn = PaymentTransaction(
        id=uuid.uuid4(),
        appointment_id=appt.id,
        gateway_order_id=f"order_{uuid.uuid4().hex[:14]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:14]}",
        amount=fee,
        currency="INR",
        status=PaymentTransactionStatus.CAPTURED,
    )
    session.add(txn)
    await session.commit()
    await session.refresh(appt)
    return appt, doctor, patient


@pytest.mark.asyncio
async def test_cancellation_with_refund_when_outside_cutoff(db_session: AsyncSession):
    policy = CancellationPolicy(
        id=uuid.uuid4(),
        name="Test 2h Full Refund",
        cutoff_hours=2,
        refund_percentage=Decimal("100.00"),
        fee_deduction=Decimal("0.00"),
        is_active=True,
    )
    db_session.add(policy)
    await db_session.commit()

    appt, doctor, patient = await _setup_confirmed_paid_appointment(
        db_session, hours_until_slot=3.0
    )

    eligible, refund_amount = await evaluate_cancellation(
        appt, policy=policy, session=db_session
    )
    assert eligible is True
    assert refund_amount == Decimal("500.00")

    result = await process_cancellation(
        appointment_id=appt.id,
        reason="Patient schedule conflict — cancelling 3 hours ahead.",
        user_id=patient.id,
        session=db_session,
    )
    assert result["status"] == AppointmentStatus.CANCELLED.value
    assert result["is_refunded"] is True
    assert result["refund_amount"] == Decimal("500.00")
    assert result["refund_id"] is not None

    await db_session.refresh(appt)
    assert appt.status == AppointmentStatus.CANCELLED
    assert appt.payment_status == PaymentStatus.REFUNDED

    txn = (
        await db_session.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.appointment_id == appt.id
            )
        )
    ).scalar_one()
    assert txn.status == PaymentTransactionStatus.REFUNDED
    assert txn.refund_id == result["refund_id"]


@pytest.mark.asyncio
async def test_cancellation_within_cutoff_no_refund(db_session: AsyncSession):
    policy = CancellationPolicy(
        id=uuid.uuid4(),
        name="Test Strict Cutoff",
        cutoff_hours=2,
        refund_percentage=Decimal("100.00"),
        fee_deduction=Decimal("0.00"),
        is_active=True,
    )
    db_session.add(policy)
    await db_session.commit()

    appt, doctor, patient = await _setup_confirmed_paid_appointment(
        db_session, hours_until_slot=0.5
    )

    eligible, refund_amount = await evaluate_cancellation(
        appt, policy=policy, session=db_session
    )
    assert eligible is False
    assert refund_amount == Decimal("0.00")

    result = await process_cancellation(
        appointment_id=appt.id,
        reason="Late cancellation within cutoff window.",
        user_id=patient.id,
        session=db_session,
    )
    assert result["status"] == AppointmentStatus.CANCELLED.value
    assert result["is_refunded"] is False
    assert result["refund_amount"] == Decimal("0.00")

    await db_session.refresh(appt)
    assert appt.status == AppointmentStatus.CANCELLED
    assert appt.payment_status == PaymentStatus.CAPTURED  # fee retained


@pytest.mark.asyncio
async def test_cancelled_slot_immediately_rebookable(db_session: AsyncSession):
    policy = CancellationPolicy(
        id=uuid.uuid4(),
        name="Rebook Policy",
        cutoff_hours=2,
        refund_percentage=Decimal("100.00"),
        fee_deduction=Decimal("0.00"),
        is_active=True,
    )
    db_session.add(policy)
    await db_session.commit()

    appt, doctor, patient = await _setup_confirmed_paid_appointment(
        db_session, hours_until_slot=4.0
    )
    slot_start = appt.slot_start
    slot_end = appt.slot_end
    query_date = slot_start.date()

    # Slot should not appear while confirmed appointment holds it
    before = await generate_slots(
        doctor_id=doctor.user_id,
        query_date=query_date,
        mode="in_person",
        session=db_session,
    )
    matching = [s for s in before if s.start_time == slot_start]
    assert matching == []

    await process_cancellation(
        appointment_id=appt.id,
        reason="Cancelling so another patient can take the slot.",
        user_id=patient.id,
        session=db_session,
    )

    after = await generate_slots(
        doctor_id=doctor.user_id,
        query_date=query_date,
        mode="in_person",
        session=db_session,
    )
    matching_after = [s for s in after if s.start_time == slot_start]
    assert len(matching_after) == 1

    # Another patient can reserve the freed slot
    other = User(
        id=uuid.uuid4(),
        phone_number=f"+9196{random_digits(8)}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(other)
    await db_session.commit()

    reserved = await reserve_slot(
        other.id,
        BookingReserveRequest(
            doctor_id=doctor.user_id,
            slot_start=slot_start,
            slot_end=slot_end,
            mode=AppointmentMode.IN_PERSON,
        ),
        db_session,
    )
    assert reserved.status == AppointmentStatus.REQUESTED

    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    signature = payment_gateway.generate_test_signature(reserved.order_id, payment_id)
    confirmed = await confirm_booking(
        BookingConfirmRequest(
            appointment_id=reserved.appointment_id,
            gateway_order_id=reserved.order_id,
            gateway_payment_id=payment_id,
            gateway_signature=signature,
        ),
        db_session,
    )
    assert confirmed.status == AppointmentStatus.CONFIRMED
