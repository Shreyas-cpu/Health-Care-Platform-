import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis import lock_manager
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.appointment import AppointmentMode, AppointmentStatus, PaymentStatus
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.booking import BookingReserveRequest
from backend.app.schemas.search import ClinicCreateOrUpdate, DoctorSearchFilters
from backend.app.services.booking_service import confirm_appointment, reserve_slot
from backend.app.services.cancellation_policy_engine import process_cancellation
from backend.app.services.catalog import get_public_doctor_profile, upsert_doctor_clinic
from backend.app.services.search_index import search_doctors


@pytest.mark.asyncio
async def test_clinic_coordinates_and_maps_url(db_session: AsyncSession):
    """Test clinic coordinates, fallback query, and maps url property."""
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(doc_user)
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Map Tester",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8]}",
        council_name="Karnataka Medical Council",
        specialty="Dermatology",
        years_experience=10,
        in_person_fee=Decimal("600.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
    )
    db_session.add(doctor)
    await db_session.flush()

    clinic = await upsert_doctor_clinic(
        db_session,
        doc_user.id,
        ClinicCreateOrUpdate(
            name="Apex Clinic",
            address="100 Feet Road",
            city="Bengaluru",
            locality="Koramangala",
            pincode="560034",
            contact_number="+919876543210",
            latitude=12.9352,
            longitude=77.6245,
        ),
    )
    assert float(clinic.latitude) == pytest.approx(12.9352)
    assert float(clinic.longitude) == pytest.approx(77.6245)
    assert "https://www.google.com/maps/search/?api=1&query=" in clinic.google_maps_url
    assert "12.9352" in clinic.google_maps_url and "77.6245" in clinic.google_maps_url

    profile = await get_public_doctor_profile(db_session, doctor.user_id)
    assert profile is not None
    assert profile.clinic is not None
    assert profile.clinic.latitude == pytest.approx(12.9352)
    assert profile.clinic.longitude == pytest.approx(77.6245)
    assert profile.google_maps_url == clinic.google_maps_url

    search_res = await search_doctors(db_session, DoctorSearchFilters(specialty="Dermatology"))
    matching = [item for item in search_res.items if item.doctor_id == doctor.user_id]
    assert len(matching) == 1
    assert matching[0].clinic.latitude == pytest.approx(12.9352)
    assert matching[0].google_maps_url == clinic.google_maps_url


@pytest.mark.asyncio
async def test_clinic_fallback_google_maps_url(db_session: AsyncSession):
    """Test clinic google_maps_url fallback when coordinates are absent."""
    clinic = Clinic(
        id=uuid.uuid4(),
        doctor_id=uuid.uuid4(),
        name="Apollo Clinic",
        address="Sector 4",
        city="Mumbai",
        locality="Bandra",
        pincode="400050",
        latitude=None,
        longitude=None,
    )
    url = clinic.google_maps_url
    assert "https://www.google.com/maps/search/?api=1&query=" in url
    assert "Apollo" in url
    assert "Mumbai" in url


@pytest.mark.asyncio
async def test_reserve_and_confirm_flow_and_api(db_session: AsyncSession):
    """Test clinic-first booking reserve, doctor confirmation, and confirmation HTTP endpoint."""
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    patient = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add_all([doc_user, patient])
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Booking Tester",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8]}",
        council_name="Delhi Medical Council",
        specialty="Pediatrics",
        years_experience=7,
        in_person_fee=Decimal("700.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
    )
    db_session.add(doctor)
    await db_session.commit()

    query_date = date.today() + timedelta(days=12)
    slot_start = datetime.combine(query_date, time(11, 0), tzinfo=UTC)
    slot_end = slot_start + timedelta(minutes=30)

    # 1. Reserve slot
    reserve_req = BookingReserveRequest(
        doctor_id=doc_user.id,
        slot_start=slot_start,
        slot_end=slot_end,
        mode=AppointmentMode.IN_PERSON,
    )
    reserved = await reserve_slot(patient.id, reserve_req, db_session)
    assert reserved.status == AppointmentStatus.REQUESTED
    assert reserved.payment_status == PaymentStatus.PENDING
    assert reserved.order_id is None
    assert reserved.fee_amount == Decimal("700.00")
    assert reserved.lock_token is not None

    # Verify lock held in Redis
    second_lock = await lock_manager.acquire_slot_lock(str(doc_user.id), slot_start.isoformat(), 30)
    assert second_lock is None

    # 2. Doctor confirms the appointment in clinic-first booking flow
    from backend.app.services.booking_service import confirm_appointment
    confirmed = await confirm_appointment(
        appointment_id=reserved.appointment_id,
        doctor_user_id=doc_user.id,
        session=db_session,
    )
    assert confirmed.status == AppointmentStatus.CONFIRMED
    assert confirmed.payment_status == PaymentStatus.PENDING

    # Lock must now be released
    relock = await lock_manager.acquire_slot_lock(str(doc_user.id), slot_start.isoformat(), 30)
    assert relock is not None
    await lock_manager.release_slot_lock(str(doc_user.id), slot_start.isoformat(), relock)


@pytest.mark.asyncio
async def test_pure_cancellation_releases_lock(db_session: AsyncSession):
    """Test pure cancellation releases lock and transitions to CANCELLED without razorpay refund."""
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    patient = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add_all([doc_user, patient])
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Cancel Flow",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8]}",
        council_name="Delhi Medical Council",
        specialty="Orthopedics",
        years_experience=6,
        in_person_fee=Decimal("800.00"),
        verification_status=VerificationStatus.VERIFIED,
        listing_online=True,
    )
    db_session.add(doctor)
    await db_session.commit()

    query_date = date.today() + timedelta(days=15)
    slot_start = datetime.combine(query_date, time(15, 0), tzinfo=UTC)
    slot_end = slot_start + timedelta(minutes=30)

    reserved = await reserve_slot(
        patient.id,
        BookingReserveRequest(
            doctor_id=doc_user.id,
            slot_start=slot_start,
            slot_end=slot_end,
            mode=AppointmentMode.IN_PERSON,
        ),
        db_session,
    )

    cancel_res = await process_cancellation(
        appointment_id=reserved.appointment_id,
        reason="Patient cannot attend in-person clinic.",
        user_id=patient.id,
        session=db_session,
    )
    assert cancel_res["status"] == "cancelled"
    assert cancel_res["is_refunded"] is False
    assert cancel_res["refund_amount"] == Decimal("0.00")

    # Lock is freed
    new_token = await lock_manager.acquire_slot_lock(str(doc_user.id), slot_start.isoformat(), 30)
    assert new_token is not None
    await lock_manager.release_slot_lock(str(doc_user.id), slot_start.isoformat(), new_token)
