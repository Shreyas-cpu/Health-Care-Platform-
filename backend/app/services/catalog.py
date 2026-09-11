from decimal import Decimal
import uuid

from backend.app.core.redis import publish_event
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.schemas.search import (
    ClinicCreateOrUpdate,
    ClinicRead,
    DoctorPublicProfile,
)
from backend.app.services.search_index import invalidate_search_cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


def _clinic_read(clinic: Clinic | None) -> ClinicRead | None:
    return ClinicRead.model_validate(clinic) if clinic else None


async def get_public_doctor_profile(
    session: AsyncSession, doctor_id: uuid.UUID
) -> DoctorPublicProfile | None:
    """Load a doctor profile and its clinic for public presentation."""
    doctor = (await session.execute(
        select(Doctor).options(selectinload(Doctor.clinic)).where(Doctor.user_id == doctor_id)
    )).scalar_one_or_none()
    if not doctor:
        return None
    clinic = _clinic_read(doctor.clinic)
    return DoctorPublicProfile(
        doctor_id=doctor.user_id, full_name=doctor.full_name, specialty=doctor.specialty,
        years_experience=doctor.years_experience, bio=doctor.bio, gender=doctor.gender,
        in_person_fee=doctor.in_person_fee, video_fee=doctor.video_fee or Decimal("0.00"),
        listing_online=doctor.listing_online, video_enabled=doctor.video_enabled,
        clinic=clinic,
        latitude=clinic.latitude if clinic else None,
        longitude=clinic.longitude if clinic else None,
        google_maps_url=clinic.google_maps_url if clinic else None,
    )


async def upsert_doctor_clinic(
    session: AsyncSession, doctor_id: uuid.UUID, data: ClinicCreateOrUpdate
) -> Clinic:
    clinic = (await session.execute(select(Clinic).where(Clinic.doctor_id == doctor_id))).scalar_one_or_none()
    if clinic is None:
        clinic = Clinic(doctor_id=doctor_id, **data.model_dump())
        session.add(clinic)
    else:
        for field, value in data.model_dump().items():
            setattr(clinic, field, value)
    await session.commit()
    await session.refresh(clinic)
    await invalidate_search_cache()
    return clinic


async def _doctor_or_raise(session: AsyncSession, doctor_id: uuid.UUID) -> Doctor:
    doctor = (await session.execute(select(Doctor).where(Doctor.user_id == doctor_id))).scalar_one_or_none()
    if not doctor:
        raise ValueError("Doctor profile not found.")
    return doctor


async def _publish_visibility(doctor: Doctor) -> None:
    try:
        await publish_event("doctor:events", "doctor_visibility_toggled", {
            "doctor_id": str(doctor.user_id),
            "listing_online": doctor.listing_online,
            "video_enabled": doctor.video_enabled,
        })
    except Exception:
        # Redis notifications supplement the DB-backed catalog; they must not make updates fail.
        pass


async def toggle_doctor_listing(
    session: AsyncSession, doctor_id: uuid.UUID, listing_online: bool | None = None
) -> Doctor:
    doctor = await _doctor_or_raise(session, doctor_id)
    target = not doctor.listing_online if listing_online is None else listing_online
    if target and doctor.verification_status != VerificationStatus.VERIFIED:
        raise ValueError("Doctor profile must be 'verified' before going online.")
    doctor.listing_online = target
    await session.commit()
    await session.refresh(doctor)
    await invalidate_search_cache()
    await _publish_visibility(doctor)
    return doctor


async def toggle_doctor_video(
    session: AsyncSession, doctor_id: uuid.UUID, video_enabled: bool | None = None
) -> Doctor:
    doctor = await _doctor_or_raise(session, doctor_id)
    target = not doctor.video_enabled if video_enabled is None else video_enabled
    if target and doctor.verification_status != VerificationStatus.VERIFIED:
        raise ValueError("Doctor profile must be 'verified' before offering video consultations.")
    doctor.video_enabled = target
    await session.commit()
    await session.refresh(doctor)
    await invalidate_search_cache()
    await _publish_visibility(doctor)
    return doctor
