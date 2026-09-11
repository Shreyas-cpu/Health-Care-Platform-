"""Phase 03 catalog, visibility, and patient identity integration tests."""
import time
import uuid
from decimal import Decimal

import pytest
from backend.app.api.v1 import patient_auth
from backend.app.models.consent import ConsentRecord
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.patient import Patient
from backend.app.models.user import User, UserRole
from backend.app.schemas.patient import SendOTPRequest, VerifyOTPRequest
from backend.app.schemas.search import ClinicCreateOrUpdate, DoctorSearchFilters
from backend.app.services.catalog import (
    get_public_doctor_profile,
    toggle_doctor_listing,
    toggle_doctor_video,
    upsert_doctor_clinic,
)
from backend.app.services.search_index import search_doctors
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request


async def _doctor(
    session: AsyncSession,
    *,
    specialty: str = "Cardiology",
    city: str = "Bengaluru",
    verified: bool = True,
    online: bool = True,
    video: bool = True,
) -> Doctor:
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True
    )
    session.add(user)
    await session.flush()

    doctor = Doctor(
        user_id=user_id, full_name="Dr. Ada Lovelace", medical_reg_number=f"REG-{uuid.uuid4()}",
        council_name="State Medical Council", specialty=specialty, years_experience=12,
        bio="Patient-focused cardiac care.", gender="female", in_person_fee=Decimal("750.00"),
        video_fee=Decimal("600.00"),
        verification_status=VerificationStatus.VERIFIED if verified else VerificationStatus.SUBMITTED,
        listing_online=online, video_enabled=video,
    )
    session.add(doctor)
    await session.flush()
    await upsert_doctor_clinic(session, user_id, ClinicCreateOrUpdate(
        name="Lovelace Clinic", address="1 Health Street", city=city, locality="Indiranagar",
        pincode="560038", contact_number="+919999999999",
    ))
    return doctor


@pytest.mark.asyncio
async def test_patient_auth_and_dpdp_consent(db_session: AsyncSession):
    """OTP verification creates the user, profile, consent record, and JWT response."""
    phone = f"+9195{uuid.uuid4().int % 100000000:08d}"
    request = Request({"type": "http", "client": ("127.0.0.1", 8000), "headers": []})
    
    # 1. Send OTP
    send_resp = await patient_auth.send_otp(SendOTPRequest(phone_number=phone))
    assert send_resp["success"] is True

    # 2. Verify with code '000000'
    response = await patient_auth.verify_otp(
        VerifyOTPRequest(phone_number=phone, otp_code="000000", full_name="Patient One"),
        request,
        db_session
    )

    assert response.access_token and response.patient.full_name == "Patient One"
    user = (await db_session.execute(select(User).where(User.phone_number == phone))).scalar_one()
    assert (await db_session.execute(select(Patient).where(Patient.user_id == user.id))).scalar_one().full_name == "Patient One"
    persisted = (await db_session.execute(select(ConsentRecord).where(ConsentRecord.user_id == user.id))).scalar_one()
    assert persisted.purpose == "patient_registration_and_care" and persisted.is_granted is True


@pytest.mark.asyncio
async def test_search_filters_and_rul02_verification_gate(db_session: AsyncSession):
    spec = f"Cardio-{uuid.uuid4().hex[:8]}"
    visible = await _doctor(db_session, specialty=spec)
    unverified = await _doctor(db_session, specialty=spec, verified=False, online=True)
    offline = await _doctor(db_session, specialty=spec, verified=True, online=False)
    
    response = await search_doctors(db_session, DoctorSearchFilters(
        specialty=spec, city="Bengaluru", min_fee=Decimal(700), max_fee=Decimal(800), gender="female",
    ))
    result_ids = [item.doctor_id for item in response.items]
    assert result_ids == [visible.user_id]
    assert unverified.user_id not in result_ids
    assert offline.user_id not in result_ids


@pytest.mark.asyncio
async def test_realtime_visibility_toggle_invalidation(db_session: AsyncSession):
    spec = f"Toggle-{uuid.uuid4().hex[:8]}"
    doctor = await _doctor(db_session, specialty=spec)
    res1 = await search_doctors(db_session, DoctorSearchFilters(specialty=spec))
    assert doctor.user_id in {item.doctor_id for item in res1.items}

    started = time.perf_counter()
    await toggle_doctor_listing(db_session, doctor.user_id, False)
    response = await search_doctors(db_session, DoctorSearchFilters(specialty=spec))
    assert time.perf_counter() - started < 0.2
    assert doctor.user_id not in {item.doctor_id for item in response.items}


@pytest.mark.asyncio
async def test_video_enabled_toggle_invalidation(db_session: AsyncSession):
    spec = f"Video-{uuid.uuid4().hex[:8]}"
    doctor = await _doctor(db_session, specialty=spec, video=True)
    res1 = await search_doctors(db_session, DoctorSearchFilters(specialty=spec, video_available=True))
    assert doctor.user_id in {item.doctor_id for item in res1.items}

    await toggle_doctor_video(db_session, doctor.user_id, False)
    response = await search_doctors(db_session, DoctorSearchFilters(specialty=spec, video_available=True))
    assert doctor.user_id not in {item.doctor_id for item in response.items}


@pytest.mark.asyncio
async def test_public_doctor_profile(db_session: AsyncSession):
    doctor = await _doctor(db_session)
    profile = await get_public_doctor_profile(db_session, doctor.user_id)
    assert profile is not None
    assert profile.bio == "Patient-focused cardiac care."
    assert profile.clinic and profile.clinic.name == "Lovelace Clinic"
    assert profile.qualifications == ["MBBS"]
    assert profile.in_person_fee == Decimal("750.00")
