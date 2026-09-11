import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.security import create_access_token, decode_token, get_password_hash
from backend.app.models.consent import ConsentRecord
from backend.app.models.user import User, UserRole
from backend.app.services.identity_service import identity_service

@pytest.mark.asyncio
async def test_user_roles(db_session: AsyncSession):
    roles = [
        UserRole.PATIENT,
        UserRole.DOCTOR,
        UserRole.VERIFICATION_REVIEWER,
        UserRole.SUPER_ADMIN,
    ]
    for r in roles:
        user = User(
            id=uuid.uuid4(),
            phone_number=f"+919{uuid.uuid4().int % 1000000000:09d}",
            role=r,
            is_active=True
        )
        db_session.add(user)
    await db_session.commit()

@pytest.mark.asyncio
async def test_jwt_issuance_and_decoding():
    user_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id, role="doctor", extra_claims={"specialty": "Cardiology"})
    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "doctor"
    assert payload["specialty"] == "Cardiology"
    assert "exp" in payload
    assert "iat" in payload

@pytest.mark.asyncio
async def test_otp_flow_with_dpdp_consent(db_session: AsyncSession):
    phone = f"+9199{uuid.uuid4().int % 100000000:08d}"
    
    # 1. Request OTP
    success, msg = await identity_service.request_otp(phone, purpose="registration")
    assert success is True

    # 2. Verify with code '000000' (test bypass)
    token_resp = await identity_service.verify_otp(
        phone_number=phone,
        otp_code="000000",
        role=UserRole.PATIENT,
        session=db_session,
        ip_address="127.0.0.1",
        consent_version="1.0"
    )

    assert token_resp.access_token is not None
    assert token_resp.user.phone_number == phone
    assert token_resp.user.role == UserRole.PATIENT

    # 3. Verify DPDP Act ConsentRecord (CMP-02) was persisted
    stmt = select(ConsentRecord).where(ConsentRecord.user_id == token_resp.user.id)
    result = await db_session.execute(stmt)
    consent = result.scalar_one_or_none()

    assert consent is not None
    assert consent.purpose == "patient_registration_and_care"
    assert consent.consent_version == "1.0"
    assert consent.is_granted is True
    assert consent.ip_address == "127.0.0.1"

@pytest.mark.asyncio
async def test_admin_password_authentication(db_session: AsyncSession):
    admin_phone = f"+9188{uuid.uuid4().int % 100000000:08d}"
    raw_password = "SuperSecureAdminPassword2026!"

    admin_user = User(
        id=uuid.uuid4(),
        phone_number=admin_phone,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        hashed_password=get_password_hash(raw_password)
    )
    db_session.add(admin_user)
    await db_session.commit()

    # Authenticate
    token_resp = await identity_service.authenticate_admin(
        phone_number=admin_phone,
        password=raw_password,
        session=db_session
    )
    assert token_resp.access_token is not None
    assert token_resp.user.role == UserRole.SUPER_ADMIN
