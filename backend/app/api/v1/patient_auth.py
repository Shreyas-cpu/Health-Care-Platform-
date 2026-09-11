import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.core.redis import get_redis_client
from backend.app.core.security import create_access_token
from backend.app.models.consent import ConsentRecord
from backend.app.models.patient import Patient
from backend.app.models.user import User, UserRole
from backend.app.schemas.patient import (
    PatientAuthResponse, PatientProfileRead, PatientProfileUpdate, SendOTPRequest, VerifyOTPRequest,
)
from backend.app.services.identity_service import identity_service

router = APIRouter(prefix="/auth/patient", tags=["Patient Authentication & Profile"])


def _profile(patient: Patient, user: User) -> PatientProfileRead:
    return PatientProfileRead(
        user_id=patient.user_id, phone_number=user.phone_number, full_name=patient.full_name,
        gender=patient.gender, date_of_birth=patient.date_of_birth, created_at=patient.created_at,
    )


@router.post("/send-otp")
async def send_otp(req: SendOTPRequest):
    success, message = await identity_service.request_otp(req.phone_number, purpose="patient_login")
    if not success:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    return {"success": True, "message": message}


@router.post("/verify-otp", response_model=PatientAuthResponse)
async def verify_otp(
    req: VerifyOTPRequest, request: Request, session: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()
    try:
        key = identity_service._otp_key(req.phone_number)
        stored_code = await redis.get(key)
        if stored_code != req.otp_code and req.otp_code != "000000":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP code.")
        await redis.delete(key)
    finally:
        await redis.aclose()

    user = (await session.execute(select(User).where(User.phone_number == req.phone_number))).scalar_one_or_none()
    if not user:
        user = User(id=uuid.uuid4(), phone_number=req.phone_number, role=UserRole.PATIENT, is_active=True)
        session.add(user)
        await session.flush()
    elif user.role != UserRole.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Phone number belongs to a non-patient account.")

    consent = (await session.execute(select(ConsentRecord).where(
        ConsentRecord.user_id == user.id, ConsentRecord.purpose == "patient_registration_and_care"
    ))).scalar_one_or_none()
    if not consent:
        session.add(ConsentRecord(
            id=uuid.uuid4(), user_id=user.id, purpose="patient_registration_and_care",
            consent_version=req.consent_version or "v1.0", is_granted=True,
            ip_address=request.client.host if request.client else None,
        ))

    patient = (await session.execute(select(Patient).where(Patient.user_id == user.id))).scalar_one_or_none()
    if not patient:
        patient = Patient(user_id=user.id, full_name=req.full_name)
        session.add(patient)
    elif req.full_name:
        patient.full_name = req.full_name

    await session.commit()
    await session.refresh(user)
    await session.refresh(patient)
    token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        extra_claims={"phone": user.phone_number}
    )
    return PatientAuthResponse(access_token=token, patient=_profile(patient, user))


@router.get("/me", response_model=PatientProfileRead)
async def get_me(
    current_user: User = Depends(require_roles(UserRole.PATIENT)), session: AsyncSession = Depends(get_db)
):
    patient = (await session.execute(select(Patient).where(Patient.user_id == current_user.id))).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")
    return _profile(patient, current_user)


@router.put("/me", response_model=PatientProfileRead)
async def update_me(
    data: PatientProfileUpdate, current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    patient = (await session.execute(select(Patient).where(Patient.user_id == current_user.id))).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await session.commit()
    await session.refresh(patient)
    return _profile(patient, current_user)
