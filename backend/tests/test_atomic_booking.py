import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from backend.app.core.config import settings
from backend.app.core.redis import lock_manager
from backend.app.models.appointment import (
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.models.schedule import DoctorAvailability, DoctorLeave
from backend.app.models.user import User, UserRole
from backend.app.schemas.booking import BookingConfirmRequest, BookingReserveRequest
from backend.app.services.booking_service import confirm_appointment, confirm_booking, reserve_slot
from backend.app.services.payment_gateway import payment_gateway
from backend.app.services.schedule_engine import generate_slots
from backend.tests.conftest import random_digits
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


async def _seed_doctor_with_availability(
    session: AsyncSession,
    query_date: date,
    *,
    start: time = time(9, 0),
    end: time = time(12, 0),
    duration: int = 30,
    buffer: int = 0,
    mode: str = "both",
) -> Doctor:
    doctor_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{random_digits(8)}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    session.add(doctor_user)
    await session.flush()

    doctor = Doctor(
        user_id=doctor_user.id,
        full_name="Dr. Slot Tester",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Test Medical Council",
        specialty="General Medicine",
        years_experience=5,
        in_person_fee=Decimal("500.00"),
        video_fee=Decimal("400.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
        video_enabled=True,
    )
    session.add(doctor)

    availability = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=doctor_user.id,
        day_of_week=query_date.weekday(),
        start_time=start,
        end_time=end,
        slot_duration_minutes=duration,
        buffer_minutes=buffer,
        mode=mode,
        is_active=True,
    )
    session.add(availability)
    await session.commit()
    return doctor


@pytest.mark.asyncio
async def test_slot_generation_and_leave_filtering(db_session: AsyncSession):
    query_date = date.today() + timedelta(days=7)
    doctor = await _seed_doctor_with_availability(db_session, query_date)

    slots = await generate_slots(
        doctor_id=doctor.user_id,
        query_date=query_date,
        mode="in_person",
        session=db_session,
    )
    assert len(slots) > 0
    assert all(s.mode == "in_person" for s in slots)
    assert all(s.is_available is True for s in slots)
    assert slots[0].fee_amount == Decimal("500.00")

    # Leave day must return empty inventory
    leave = DoctorLeave(
        id=uuid.uuid4(),
        doctor_id=doctor.user_id,
        leave_date=query_date,
        reason="Conference",
    )
    db_session.add(leave)
    await db_session.commit()

    leave_slots = await generate_slots(
        doctor_id=doctor.user_id,
        query_date=query_date,
        mode="in_person",
        session=db_session,
    )
    assert leave_slots == []


@pytest.mark.asyncio
async def test_redis_locking_concurrent_booking_conflict(db_session: AsyncSession):
    """
    RUL-01: Concurrent reserve attempts on the same slot -> exactly one success, rest 409.
    """
    query_date = date.today() + timedelta(days=8)
    doctor = await _seed_doctor_with_availability(
        db_session, query_date, start=time(10, 0), end=time(11, 0), duration=30, buffer=0
    )

    slot_start = datetime.combine(query_date, time(10, 0), tzinfo=UTC)
    slot_end = slot_start + timedelta(minutes=30)

    patients = []
    for _ in range(5):
        p = User(
            id=uuid.uuid4(),
            phone_number=f"+9198{random_digits(8)}",
            role=UserRole.PATIENT,
            is_active=True,
        )
        db_session.add(p)
        patients.append(p)
    await db_session.commit()

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async def attempt_reserve(patient_id: uuid.UUID):
        async with session_factory() as session:
            req = BookingReserveRequest(
                doctor_id=doctor.user_id,
                slot_start=slot_start,
                slot_end=slot_end,
                mode=AppointmentMode.IN_PERSON,
            )
            try:
                result = await reserve_slot(patient_id, req, session)
                return ("ok", result)
            except HTTPException as exc:
                return ("err", exc.status_code, exc.detail)

    results = await asyncio.gather(
        *[attempt_reserve(p.id) for p in patients]
    )
    await engine.dispose()

    successes = [r for r in results if r[0] == "ok"]
    conflicts = [r for r in results if r[0] == "err" and r[1] == 409]

    assert len(successes) == 1
    assert len(conflicts) == len(patients) - 1
    assert all(
        "booked" in str(c[2]).lower() or "being booked" in str(c[2]).lower()
        for c in conflicts
    )

    # Cleanup Redis lock from the successful reservation
    winner = successes[0][1]
    if winner.lock_token:
        await lock_manager.release_slot_lock(
            str(doctor.user_id), slot_start.isoformat(), winner.lock_token
        )


@pytest.mark.asyncio
async def test_payment_capture_confirms_appointment_and_releases_lock(
    db_session: AsyncSession,
    sample_patient: User,
):
    """Clinic-first: Reserve + doctor confirmation confirms and releases Redis lock."""
    query_date = date.today() + timedelta(days=9)
    doctor = await _seed_doctor_with_availability(
        db_session, query_date, start=time(14, 0), end=time(15, 0), duration=30, buffer=0
    )

    slot_start = datetime.combine(query_date, time(14, 0), tzinfo=UTC)
    slot_end = slot_start + timedelta(minutes=30)

    reserved = await reserve_slot(
        sample_patient.id,
        BookingReserveRequest(
            doctor_id=doctor.user_id,
            slot_start=slot_start,
            slot_end=slot_end,
            mode=AppointmentMode.IN_PERSON,
        ),
        db_session,
    )
    assert reserved.status == AppointmentStatus.REQUESTED
    assert reserved.payment_status == PaymentStatus.PENDING
    assert reserved.order_id is None
    assert reserved.lock_token is not None

    # Lock must be held
    second = await lock_manager.acquire_slot_lock(
        str(doctor.user_id), slot_start.isoformat(), ttl_seconds=60
    )
    assert second is None

    # Doctor confirms appointment
    confirmed = await confirm_appointment(
        appointment_id=reserved.appointment_id,
        doctor_user_id=doctor.user_id,
        session=db_session,
    )
    assert confirmed.status == AppointmentStatus.CONFIRMED
    assert confirmed.payment_status == PaymentStatus.PENDING
    assert confirmed.lock_token is None

    # Redis lock released — can acquire again
    token = await lock_manager.acquire_slot_lock(
        str(doctor.user_id), slot_start.isoformat(), ttl_seconds=30
    )
    assert token is not None
    await lock_manager.release_slot_lock(
        str(doctor.user_id), slot_start.isoformat(), token
    )
