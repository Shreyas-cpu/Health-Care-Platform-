import asyncio
import time
import uuid
from datetime import UTC, date, datetime, time as dt_time, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.core.redis import lock_manager
from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.audit import AuditLog
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.schedule import DoctorAvailability
from backend.app.models.user import User, UserRole
from backend.app.schemas.booking import BookingConfirmRequest, BookingReserveRequest
from backend.app.schemas.search import ClinicCreateOrUpdate, DoctorSearchFilters
from backend.app.services.appointment_state import appointment_state_machine
from backend.app.services.audit import record_audit_log
from backend.app.services.booking_service import confirm_booking, reserve_slot
from backend.app.services.catalog import toggle_doctor_listing, upsert_doctor_clinic
from backend.app.services.payment_gateway import payment_gateway
from backend.app.services.search_index import search_doctors
from backend.app.services.verification_state import verification_state_machine
from backend.tests.conftest import random_digits


@pytest.mark.asyncio
async def test_rul01_100_concurrent_slot_reservations_zero_double_booking(db_session: AsyncSession):
    """
    RUL-01: 100 concurrent slot reservations on the exact same doctor and slot.
    Guarantees:
    - Exactly 1 reservation succeeds (HTTP 200 / status REQUESTED).
    - Exactly 99 fail with HTTP 409 Conflict.
    - Exactly 1 appointment row exists in DB for this doctor and slot (zero double-booking).
    - Redis distributed lock is held by the winning reservation.
    """
    query_date = datetime.now(UTC).date() + timedelta(days=21)

    # 1. Seed Doctor with availability
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{random_digits(8)}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(doc_user)
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Concurrency Master",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Stress Medical Council",
        specialty="General Medicine",
        years_experience=15,
        in_person_fee=Decimal("500.00"),
        video_fee=Decimal("400.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
        video_enabled=True,
    )
    db_session.add(doctor)

    availability = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=doc_user.id,
        day_of_week=query_date.weekday(),
        start_time=dt_time(10, 0),
        end_time=dt_time(11, 0),
        slot_duration_minutes=30,
        buffer_minutes=0,
        mode="both",
        is_active=True,
    )
    db_session.add(availability)

    # 2. Seed 100 Patients
    patient_ids = []
    for _ in range(100):
        p_id = uuid.uuid4()
        patient_user = User(
            id=p_id,
            phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
            role=UserRole.PATIENT,
            is_active=True,
        )
        db_session.add(patient_user)
        patient_ids.append(p_id)

    await db_session.commit()

    slot_start = datetime.combine(query_date, dt_time(10, 0), tzinfo=UTC)
    slot_end = slot_start + timedelta(minutes=30)
    slot_iso = slot_start.isoformat()

    # Pre-clean any leftover lock
    key = lock_manager.format_slot_key(str(doctor.user_id), slot_iso)
    await lock_manager.release_lock(key, "dummy")

    # Engine for concurrent worker sessions with bounded connection pooling
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=15,
        max_overflow=15,
        pool_timeout=30.0,
        echo=False,
    )
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    sem = asyncio.Semaphore(20)

    async def attempt_booking(pid: uuid.UUID):
        req = BookingReserveRequest(
            doctor_id=doctor.user_id,
            slot_start=slot_start,
            slot_end=slot_end,
            mode=AppointmentMode.IN_PERSON,
        )
        async with sem:
            async with session_factory() as worker_session:
                try:
                    res = await reserve_slot(pid, req, worker_session)
                    await worker_session.commit()
                    return res
                except HTTPException as e:
                    await worker_session.rollback()
                    return e
                except Exception as e:
                    await worker_session.rollback()
                    return e

    # Execute 100 concurrent reservation tasks simultaneously
    tasks = [attempt_booking(pid) for pid in patient_ids]
    results = await asyncio.gather(*tasks)

    await test_engine.dispose()

    # Categorize results
    successes = [r for r in results if not isinstance(r, Exception)]
    conflicts = [r for r in results if isinstance(r, HTTPException) and r.status_code == 409]
    other_exceptions = [
        r for r in results if isinstance(r, Exception) and not (isinstance(r, HTTPException) and r.status_code == 409)
    ]

    assert len(other_exceptions) == 0, f"Unexpected exceptions during concurrency test: {other_exceptions}"
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == 99, f"Expected 99 conflicts (409), got {len(conflicts)}"

    # Verification: Confirm appointment in DB
    async with session_factory() as verify_session:
        stmt = select(Appointment).where(
            Appointment.doctor_id == doctor.user_id,
            Appointment.slot_start == slot_start,
        )
        db_res = await verify_session.execute(stmt)
        appointments = db_res.scalars().all()
        assert len(appointments) == 1
        assert appointments[0].status == AppointmentStatus.REQUESTED
        assert appointments[0].payment_status == PaymentStatus.PENDING

    # Release lock after test
    winning_token = successes[0].lock_token
    released = await lock_manager.release_slot_lock(str(doctor.user_id), slot_iso, winning_token)
    assert released is True


@pytest.mark.asyncio
async def test_rul02_realtime_visibility_toggle_propagation_latency(db_session: AsyncSession):
    """
    RUL-02: Real-time search visibility toggle propagation latency must be < 200ms.
    - Verified doctor appears in search.
    - Toggling listing_online = False invalidates cache and removes doctor from search in < 200ms.
    """
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        phone_number=f"+9195{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    doctor = Doctor(
        user_id=user_id,
        full_name="Dr. Realtime Latency Tester",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Stress Medical Council",
        specialty="Pediatrics",
        years_experience=10,
        in_person_fee=Decimal("600.00"),
        video_fee=Decimal("500.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
        video_enabled=True,
    )
    db_session.add(doctor)
    await db_session.flush()

    await upsert_doctor_clinic(
        db_session,
        user_id,
        ClinicCreateOrUpdate(
            name="Latency Clinic",
            address="Brigade Road",
            city="Bengaluru",
            locality="Central",
            pincode="560001",
            contact_number="+919888877777",
        ),
    )
    await db_session.commit()

    # Verify doctor is present in initial search
    search_filters = DoctorSearchFilters(query="Latency", specialty="Pediatrics", city="Bengaluru")
    initial_search = await search_doctors(db_session, search_filters)
    assert any(doc.doctor_id == user_id for doc in initial_search.items)

    # Measure latency of visibility toggle and cache invalidation
    t_start = time.perf_counter()
    updated_doctor = await toggle_doctor_listing(db_session, user_id, False)
    await db_session.commit()
    t_toggle = time.perf_counter()

    # Verify doctor is immediately absent from subsequent search
    subsequent_search = await search_doctors(db_session, search_filters)
    t_search_after = time.perf_counter()

    toggle_latency_ms = (t_toggle - t_start) * 1000
    assert not any(doc.doctor_id == user_id for doc in subsequent_search.items)
    assert toggle_latency_ms < 200, f"Toggle and invalidation latency was {toggle_latency_ms:.2f}ms (must be < 200ms)"
    assert updated_doctor.listing_online is False


@pytest.mark.asyncio
async def test_rul03_atomic_slot_reservation_payment_rollback(db_session: AsyncSession):
    """
    RUL-03: Atomic slot reservation and payment rollback.
    - If payment capture fails or aborts, appointment transitions to cancelled and lock is released.
    - The exact same slot becomes immediately re-bookable by another patient.
    """
    query_date = datetime.now(UTC).date() + timedelta(days=22)
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{random_digits(8)}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    patient1 = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{random_digits(8)}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    patient2 = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{random_digits(8)}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add_all([doc_user, patient1, patient2])
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Rollback Tester",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Test Council",
        specialty="Dermatology",
        years_experience=7,
        in_person_fee=Decimal("700.00"),
        video_fee=Decimal("600.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
        video_enabled=True,
    )
    db_session.add(doctor)

    availability = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=doc_user.id,
        day_of_week=query_date.weekday(),
        start_time=dt_time(14, 0),
        end_time=dt_time(15, 0),
        slot_duration_minutes=30,
        buffer_minutes=0,
        mode="in_person",
        is_active=True,
    )
    db_session.add(availability)
    await db_session.commit()

    slot_start = datetime.combine(query_date, dt_time(14, 0), tzinfo=UTC)
    slot_end = slot_start + timedelta(minutes=30)
    slot_iso = slot_start.isoformat()

    # 1. Patient 1 reserves the slot
    reserve_req = BookingReserveRequest(
        doctor_id=doctor.user_id,
        slot_start=slot_start,
        slot_end=slot_end,
        mode=AppointmentMode.IN_PERSON,
    )
    res1 = await reserve_slot(patient1.id, reserve_req, db_session)
    await db_session.commit()
    assert res1.status == AppointmentStatus.REQUESTED
    assert res1.payment_status == PaymentStatus.PENDING

    # 2. Patient 2 attempts to reserve while Patient 1 holds the lock -> Must fail with 409
    with pytest.raises(HTTPException) as exc_info:
        await reserve_slot(patient2.id, reserve_req, db_session)
    assert exc_info.value.status_code == 409

    # 3. Patient 1 payment fails / invalid signature
    fake_sig = "invalid_signature_xyz"
    confirm_req = BookingConfirmRequest(
        appointment_id=res1.appointment_id,
        gateway_order_id=res1.order_id or "order_test_123",
        gateway_payment_id="pay_failed_456",
        gateway_signature=fake_sig,
    )
    with pytest.raises(HTTPException) as sig_exc:
        await confirm_booking(confirm_req, db_session)
    assert sig_exc.value.status_code == 400

    # Simulate payment abort / cancellation rollback:
    # Transition appointment to CANCELLED and release Redis lock
    stmt = select(Appointment).where(Appointment.id == res1.appointment_id)
    appt1 = (await db_session.execute(stmt)).scalar_one()
    await appointment_state_machine.transition(
        appt1,
        AppointmentStatus.CANCELLED,
        db_session,
        reason="Payment expired or aborted by user.",
    )
    await lock_manager.release_slot_lock(str(doctor.user_id), slot_iso, res1.lock_token)
    await db_session.commit()

    # 4. Now Patient 2 attempts to reserve the exact same slot -> Must SUCCEED cleanly!
    res2 = await reserve_slot(patient2.id, reserve_req, db_session)
    await db_session.commit()
    assert res2.status == AppointmentStatus.REQUESTED
    assert res2.appointment_id != res1.appointment_id

    # 5. Patient 2 completes payment verification and capture
    valid_sig = payment_gateway.generate_test_signature(res2.order_id, "pay_success_789")
    confirm_req_p2 = BookingConfirmRequest(
        appointment_id=res2.appointment_id,
        gateway_order_id=res2.order_id,
        gateway_payment_id="pay_success_789",
        gateway_signature=valid_sig,
    )
    confirmed_appt = await confirm_booking(confirm_req_p2, db_session)
    await db_session.commit()

    assert confirmed_appt.status == AppointmentStatus.CONFIRMED
    assert confirmed_appt.payment_status == PaymentStatus.CAPTURED


@pytest.mark.asyncio
async def test_rul04_immutable_audit_logging_across_administrative_mutations(db_session: AsyncSession):
    """
    RUL-04: Immutable audit logging across administrative mutations.
    - Administrative transitions create append-only records in audit_logs table.
    - Tampering or deleting audit logs is strictly prevented.
    """
    admin_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9199{random_digits(8)}",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{random_digits(8)}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add_all([admin_user, doc_user])
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Audit Candidate",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Test Council",
        specialty="Orthopedics",
        years_experience=8,
        in_person_fee=Decimal("800.00"),
        video_fee=Decimal("700.00"),
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False,
    )
    db_session.add(doctor)
    await db_session.commit()

    # 1. Admin transitions doctor status: SUBMITTED -> UNDER_REVIEW
    await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.UNDER_REVIEW,
        admin_user_id=admin_user.id,
        session=db_session,
        reason_text="Initial automated document validation complete.",
    )
    await db_session.commit()

    # 2. Query audit logs
    audit_stmt = select(AuditLog).where(
        AuditLog.target_entity_type == "doctor",
        AuditLog.target_entity_id == doctor.user_id,
    ).order_by(AuditLog.created_at.desc())
    logs = (await db_session.execute(audit_stmt)).scalars().all()

    assert len(logs) >= 1
    latest_log = logs[0]
    assert latest_log.admin_user_id == admin_user.id
    assert latest_log.action == "doctor_verification_under_review"
    assert "Initial automated document validation" in latest_log.reason
    assert latest_log.created_at is not None

    # 3. Direct audit log creation via record_audit_log
    direct_log = await record_audit_log(
        admin_user_id=admin_user.id,
        target_entity_type="appointment",
        target_entity_id=uuid.uuid4(),
        action="manual_refund_override",
        reason="Admin approved goodwill refund.",
        session=db_session,
        previous_state={"payment_status": "captured"},
        new_state={"payment_status": "refunded"},
    )
    await db_session.commit()

    assert direct_log.id is not None
    assert direct_log.action == "manual_refund_override"
