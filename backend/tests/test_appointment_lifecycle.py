import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.redis import lock_manager
from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.user import User
from backend.app.services.appointment_state import (
    InvalidStateTransitionError,
    appointment_state_machine,
)

@pytest.mark.asyncio
async def test_appointment_full_consultation_lifecycle(
    db_session: AsyncSession,
    sample_patient: User,
    sample_doctor: User
):
    now = datetime.now(timezone.utc)
    slot_start = now + timedelta(days=1)
    slot_end = slot_start + timedelta(minutes=30)

    # 1. Create Requested appointment
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=sample_patient.id,
        doctor_id=sample_doctor.id,
        mode=AppointmentMode.VIDEO,
        status=AppointmentStatus.REQUESTED,
        slot_start=slot_start,
        slot_end=slot_end,
        fee_amount=Decimal("500.00"),
        payment_status=PaymentStatus.PENDING
    )
    db_session.add(appt)
    await db_session.commit()
    await db_session.refresh(appt)
    assert appt.status == AppointmentStatus.REQUESTED

    # 2. Transition: Requested -> Confirmed
    appt = await appointment_state_machine.transition(
        appt, AppointmentStatus.CONFIRMED, db_session
    )
    appt.payment_status = PaymentStatus.CAPTURED
    await db_session.commit()
    assert appt.status == AppointmentStatus.CONFIRMED

    # 3. Transition: Confirmed -> CheckedIn
    appt = await appointment_state_machine.transition(
        appt, AppointmentStatus.CHECKED_IN, db_session
    )
    await db_session.commit()
    assert appt.status == AppointmentStatus.CHECKED_IN

    # 4. Transition: CheckedIn -> InConsultation
    appt = await appointment_state_machine.transition(
        appt, AppointmentStatus.IN_CONSULTATION, db_session
    )
    await db_session.commit()
    assert appt.status == AppointmentStatus.IN_CONSULTATION

    # 5. Transition: InConsultation -> Completed
    appt = await appointment_state_machine.transition(
        appt, AppointmentStatus.COMPLETED, db_session
    )
    await db_session.commit()
    assert appt.status == AppointmentStatus.COMPLETED

@pytest.mark.asyncio
async def test_appointment_cancellation_lifecycle(
    db_session: AsyncSession,
    sample_patient: User,
    sample_doctor: User
):
    now = datetime.now(timezone.utc)
    slot_start = now + timedelta(days=2)
    slot_end = slot_start + timedelta(minutes=30)

    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=sample_patient.id,
        doctor_id=sample_doctor.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
        slot_start=slot_start,
        slot_end=slot_end,
        fee_amount=Decimal("800.00"),
        payment_status=PaymentStatus.CAPTURED
    )
    db_session.add(appt)
    await db_session.commit()

    # Cancel with reason
    reason = "Patient had a sudden family emergency."
    appt = await appointment_state_machine.transition(
        appt, AppointmentStatus.CANCELLED, db_session, reason=reason
    )
    await db_session.commit()
    assert appt.status == AppointmentStatus.CANCELLED
    assert appt.cancellation_reason == reason

@pytest.mark.asyncio
async def test_appointment_reschedule_and_no_show(
    db_session: AsyncSession,
    sample_patient: User,
    sample_doctor: User
):
    now = datetime.now(timezone.utc)
    slot_start = now + timedelta(days=3)
    slot_end = slot_start + timedelta(minutes=30)

    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=sample_patient.id,
        doctor_id=sample_doctor.id,
        mode=AppointmentMode.VIDEO,
        status=AppointmentStatus.CONFIRMED,
        slot_start=slot_start,
        slot_end=slot_end,
        fee_amount=Decimal("600.00"),
        payment_status=PaymentStatus.CAPTURED
    )
    db_session.add(appt)
    await db_session.commit()

    # Confirmed -> Rescheduled -> Confirmed
    appt = await appointment_state_machine.transition(appt, AppointmentStatus.RESCHEDULED, db_session)
    assert appt.status == AppointmentStatus.RESCHEDULED

    appt = await appointment_state_machine.transition(appt, AppointmentStatus.CONFIRMED, db_session)
    assert appt.status == AppointmentStatus.CONFIRMED

    # Confirmed -> NoShow
    appt = await appointment_state_machine.transition(appt, AppointmentStatus.NO_SHOW, db_session)
    await db_session.commit()
    assert appt.status == AppointmentStatus.NO_SHOW

@pytest.mark.asyncio
async def test_illegal_state_transitions_raise_422(
    db_session: AsyncSession,
    sample_patient: User,
    sample_doctor: User
):
    now = datetime.now(timezone.utc)
    slot_start = now + timedelta(days=4)
    slot_end = slot_start + timedelta(minutes=30)

    # Requested appointment
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=sample_patient.id,
        doctor_id=sample_doctor.id,
        mode=AppointmentMode.VIDEO,
        status=AppointmentStatus.REQUESTED,
        slot_start=slot_start,
        slot_end=slot_end,
        fee_amount=Decimal("500.00")
    )
    db_session.add(appt)
    await db_session.commit()

    # Illegal leap: Requested -> Completed
    with pytest.raises(InvalidStateTransitionError):
        await appointment_state_machine.transition(appt, AppointmentStatus.COMPLETED, db_session)

    # Illegal leap: Requested -> InConsultation
    with pytest.raises(InvalidStateTransitionError):
        await appointment_state_machine.transition(appt, AppointmentStatus.IN_CONSULTATION, db_session)

    # Transition to terminal Completed
    await appointment_state_machine.transition(appt, AppointmentStatus.CONFIRMED, db_session)
    await appointment_state_machine.transition(appt, AppointmentStatus.CHECKED_IN, db_session)
    await appointment_state_machine.transition(appt, AppointmentStatus.IN_CONSULTATION, db_session)
    await appointment_state_machine.transition(appt, AppointmentStatus.COMPLETED, db_session)

    # Illegal transition from terminal Completed -> Confirmed
    with pytest.raises(InvalidStateTransitionError):
        await appointment_state_machine.transition(appt, AppointmentStatus.CONFIRMED, db_session)

@pytest.mark.asyncio
async def test_slot_double_booking_prevention_redis_and_db(
    db_session: AsyncSession,
    sample_patient: User,
    sample_doctor: User
):
    """
    RUL-01: Zero double-booking verification.
    1. Redis lock prevents concurrent booking requests.
    2. PostgreSQL exclusion constraint rejects overlapping active slots.
    """
    now = datetime.now(timezone.utc)
    slot_start = now + timedelta(days=5)
    slot_end = slot_start + timedelta(minutes=30)
    slot_iso = slot_start.isoformat()

    # Step 1: Redis distributed lock
    token = await lock_manager.acquire_slot_lock(str(sample_doctor.id), slot_iso, ttl_seconds=60)
    assert token is not None

    # Another concurrent lock attempt on the exact same slot must be rejected
    second_token = await lock_manager.acquire_slot_lock(str(sample_doctor.id), slot_iso, ttl_seconds=60)
    assert second_token is None

    # Step 2: Insert confirmed appointment in DB
    appt1 = Appointment(
        id=uuid.uuid4(),
        patient_id=sample_patient.id,
        doctor_id=sample_doctor.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
        slot_start=slot_start,
        slot_end=slot_end,
        fee_amount=Decimal("500.00")
    )
    db_session.add(appt1)
    await db_session.commit()

    # Release Redis lock
    released = await lock_manager.release_slot_lock(str(sample_doctor.id), slot_iso, token)
    assert released is True

    # Step 3: Attempt to insert an overlapping confirmed appointment for the same doctor
    # Even if Redis lock was released, DB exclusion constraint MUST block this!
    overlap_patient = User(
        id=uuid.uuid4(),
        phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
        role=sample_patient.role,
        is_active=True
    )
    db_session.add(overlap_patient)
    await db_session.commit()

    overlapping_start = slot_start + timedelta(minutes=10)
    overlapping_end = overlapping_start + timedelta(minutes=30)

    appt2 = Appointment(
        id=uuid.uuid4(),
        patient_id=overlap_patient.id,
        doctor_id=sample_doctor.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
        slot_start=overlapping_start,
        slot_end=overlapping_end,
        fee_amount=Decimal("500.00")
    )
    db_session.add(appt2)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.commit()

    assert "no_overlapping_doctor_appointments" in str(exc_info.value)
