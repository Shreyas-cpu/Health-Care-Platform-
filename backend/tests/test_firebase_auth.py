import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.api.v1.firebase_auth import (
    bind_phone,
    firebase_login,
    get_firebase_profile,
    verify_token,
)
from backend.app.core.security import create_access_token
from backend.app.models.consent import ConsentRecord
from backend.app.models.patient import Patient
from backend.app.models.user import User, UserRole
from backend.app.schemas.firebase_auth import (
    FirebaseBindPhoneRequest,
    FirebaseLoginRequest,
    FirebaseVerifyTokenRequest,
)
from backend.app.services.firebase_auth import (
    create_mock_firebase_token,
    sync_firebase_user,
    verify_firebase_id_token,
)
from fastapi.security import HTTPAuthorizationCredentials


class DummyClient:
    host = "127.0.0.1"


class DummyRequest:
    client = DummyClient()


@pytest.mark.asyncio
async def test_mock_firebase_token_generation_and_verification():
    """Validates that mock Firebase tokens encode and decode identity claims cleanly."""
    uid = f"fb-uid-{uuid.uuid4().hex[:12]}"
    token = create_mock_firebase_token(
        uid=uid,
        phone_number="+919876543210",
        email="patient.sharma@example.com",
        name="Aarav Sharma",
    )
    claims = verify_firebase_id_token(token)
    assert claims["uid"] == uid
    assert claims["phone_number"] == "+919876543210"
    assert claims["email"] == "patient.sharma@example.com"
    assert claims["name"] == "Aarav Sharma"


@pytest.mark.asyncio
async def test_firebase_phone_login_creates_patient_and_dpdp_consent(db_session: AsyncSession):
    """
    Tests that a new patient logging in via Firebase Phone Auth:
    1. Creates a User with role=patient and firebase_uid.
    2. Auto-provisions Patient profile.
    3. Records DPDP Act compliant ConsentRecord.
    4. Returns platform access token.
    """
    uid = f"fb-patient-{uuid.uuid4().hex[:12]}"
    phone = f"+9198{uuid.uuid4().int % 100000000:08d}"
    token = create_mock_firebase_token(
        uid=uid,
        phone_number=phone,
        name="Sunita Patil",
    )

    req = FirebaseLoginRequest(
        id_token=token,
        role=UserRole.PATIENT,
        full_name="Sunita Patil",
        consent_version="v1.0",
    )

    resp = await firebase_login(req, DummyRequest(), db_session)
    assert resp.is_new_user is True
    assert resp.role == UserRole.PATIENT
    assert resp.firebase_uid == uid
    assert resp.phone_number == phone
    assert resp.access_token is not None

    # Verify Patient profile in DB
    pat = (await db_session.execute(select(Patient).where(Patient.user_id == resp.user_id))).scalar_one_or_none()
    assert pat is not None
    assert pat.full_name == "Sunita Patil"

    # Verify DPDP consent record in DB
    consent = (await db_session.execute(
        select(ConsentRecord).where(
            ConsentRecord.user_id == resp.user_id,
            ConsentRecord.purpose == "patient_registration_and_care",
        )
    )).scalar_one_or_none()
    assert consent is not None
    assert consent.is_granted is True
    assert consent.consent_version == "v1.0"


@pytest.mark.asyncio
async def test_firebase_google_login_with_email(db_session: AsyncSession):
    """
    Tests that a doctor signing in with Google:
    1. Successfully authenticates with email (without phone initially).
    2. Creates User with role=doctor and email stored.
    """
    uid = f"fb-doc-{uuid.uuid4().hex[:12]}"
    email = f"dr.kulkarni_{uuid.uuid4().hex[:6]}@clinic.org"
    token = create_mock_firebase_token(
        uid=uid,
        email=email,
        name="Dr. Ramesh Kulkarni",
        role="doctor",
    )

    req = FirebaseLoginRequest(
        id_token=token,
        role=UserRole.DOCTOR,
        full_name="Dr. Ramesh Kulkarni",
    )

    resp = await firebase_login(req, DummyRequest(), db_session)
    assert resp.is_new_user is True
    assert resp.role == UserRole.DOCTOR
    assert resp.email == email
    assert resp.phone_number is None

    user = (await db_session.execute(select(User).where(User.id == resp.user_id))).scalar_one_or_none()
    assert user is not None
    assert user.firebase_uid == uid
    assert user.email == email


@pytest.mark.asyncio
async def test_firebase_repeat_login_is_idempotent(db_session: AsyncSession):
    """Tests that subsequent logins with the same Firebase UID return is_new_user=False."""
    uid = f"fb-repeat-{uuid.uuid4().hex[:12]}"
    phone = f"+9191{uuid.uuid4().int % 100000000:08d}"
    token = create_mock_firebase_token(uid=uid, phone_number=phone, name="Repeat User")

    req = FirebaseLoginRequest(id_token=token, role=UserRole.PATIENT)

    # First login
    resp1 = await firebase_login(req, DummyRequest(), db_session)
    assert resp1.is_new_user is True

    # Second login
    resp2 = await firebase_login(req, DummyRequest(), db_session)
    assert resp2.is_new_user is False
    assert resp2.user_id == resp1.user_id
    assert resp2.firebase_uid == uid


@pytest.mark.asyncio
async def test_firebase_links_existing_user_by_phone(db_session: AsyncSession):
    """
    Tests that a user already in the database (e.g. from prior SMS OTP)
    gets seamlessly linked with their Firebase UID on first Firebase login.
    """
    phone = f"+9194{uuid.uuid4().int % 100000000:08d}"
    existing_user = User(
        id=uuid.uuid4(),
        phone_number=phone,
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(existing_user)
    await db_session.commit()

    fb_uid = f"fb-link-{uuid.uuid4().hex[:12]}"
    token = create_mock_firebase_token(uid=fb_uid, phone_number=phone)

    req = FirebaseLoginRequest(id_token=token, role=UserRole.PATIENT)
    resp = await firebase_login(req, DummyRequest(), db_session)

    assert resp.is_new_user is False
    assert resp.user_id == existing_user.id
    assert resp.firebase_uid == fb_uid

    # Verify DB column updated
    await db_session.refresh(existing_user)
    assert existing_user.firebase_uid == fb_uid


@pytest.mark.asyncio
async def test_firebase_verify_endpoint():
    """Tests token inspection endpoint."""
    uid = f"fb-verify-{uuid.uuid4().hex[:12]}"
    token = create_mock_firebase_token(
        uid=uid,
        email="verify@test.local",
        phone_number="+919988776655",
        name="Verify Tester",
    )
    res = await verify_token(FirebaseVerifyTokenRequest(id_token=token))
    assert res.valid is True
    assert res.uid == uid
    assert res.email == "verify@test.local"
    assert res.phone_number == "+919988776655"
    assert res.name == "Verify Tester"


@pytest.mark.asyncio
async def test_firebase_bind_phone_endpoint(db_session: AsyncSession):
    """Tests binding a phone number to an email-authenticated user."""
    user = User(
        id=uuid.uuid4(),
        email=f"nophone_{uuid.uuid4().hex[:6]}@test.local",
        firebase_uid=f"fb-bind-{uuid.uuid4().hex[:8]}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    new_phone = f"+9195{uuid.uuid4().int % 100000000:08d}"
    resp = await bind_phone(FirebaseBindPhoneRequest(phone_number=new_phone), user, db_session)
    assert resp["success"] is True
    assert resp["phone_number"] == new_phone

    await db_session.refresh(user)
    assert user.phone_number == new_phone


@pytest.mark.asyncio
async def test_dual_mode_auth_in_deps(db_session: AsyncSession):
    """
    Tests that get_current_user resolves the authenticated user via BOTH:
    1. Direct Firebase ID token in Authorization header.
    2. Platform JWT access token in Authorization header.
    """
    uid = f"fb-dual-{uuid.uuid4().hex[:12]}"
    user = User(
        id=uuid.uuid4(),
        firebase_uid=uid,
        phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # Case A: Authenticate using platform JWT token
    platform_token = create_access_token(subject=str(user.id), role=user.role.value)
    creds_jwt = HTTPAuthorizationCredentials(scheme="Bearer", credentials=platform_token)
    resolved_user_jwt = await get_current_user(creds_jwt, db_session)
    assert resolved_user_jwt.id == user.id

    # Case B: Authenticate using direct Firebase ID token
    fb_token = create_mock_firebase_token(uid=uid, phone_number=user.phone_number)
    creds_fb = HTTPAuthorizationCredentials(scheme="Bearer", credentials=fb_token)
    resolved_user_fb = await get_current_user(creds_fb, db_session)
    assert resolved_user_fb.id == user.id


@pytest.mark.asyncio
async def test_deactivated_user_forbidden(db_session: AsyncSession):
    """Tests that deactivated accounts return 403 Forbidden even with valid Firebase token."""
    uid = f"fb-deactivated-{uuid.uuid4().hex[:12]}"
    user = User(
        id=uuid.uuid4(),
        firebase_uid=uid,
        phone_number=f"+9190{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=False,  # Suspended
    )
    db_session.add(user)
    await db_session.commit()

    fb_token = create_mock_firebase_token(uid=uid, phone_number=user.phone_number)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=fb_token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds, db_session)
    assert exc_info.value.status_code == 403
    assert "deactivated" in exc_info.value.detail.lower()
