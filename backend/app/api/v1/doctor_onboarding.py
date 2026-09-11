import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, require_roles
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.redis import publish_event
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.user import User, UserRole
from backend.app.models.verification import DoctorDocument
from backend.app.schemas.doctor import DoctorRead, DoctorRegisterRequest, DoctorVisibilityUpdate
from backend.app.schemas.verification import (
    DoctorDocumentRead,
    DocumentConfirmRequest,
    DocumentPresignRequest,
    DocumentPresignResponse,
)
from backend.app.services.storage import storage_service

router = APIRouter(prefix="/doctors", tags=["Doctor Onboarding & Practice Management"])

@router.post("/register", response_model=DoctorRead, status_code=status.HTTP_201_CREATED)
async def register_doctor(
    req: DoctorRegisterRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db)
):
    """
    Submits doctor professional profile attached to Phase 01 User identity.
    Initial status is 'submitted'.
    """
    stmt = select(Doctor).where(Doctor.user_id == current_user.id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor profile already registered for this user."
        )

    # Check unique registration number
    stmt_reg = select(Doctor).where(Doctor.medical_reg_number == req.medical_reg_number)
    duplicate_reg = (await session.execute(stmt_reg)).scalar_one_or_none()
    if duplicate_reg:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Medical council registration number already registered."
        )

    doctor = Doctor(
        user_id=current_user.id,
        full_name=req.full_name,
        medical_reg_number=req.medical_reg_number,
        council_name=req.council_name,
        specialty=req.specialty,
        years_experience=req.years_experience,
        bio=req.bio,
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False,
        video_enabled=False
    )
    session.add(doctor)
    await session.commit()
    await session.refresh(doctor)
    return doctor

@router.post("/documents/presign", response_model=DocumentPresignResponse)
async def presign_document_upload(
    req: DocumentPresignRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR))
):
    """
    Generates pre-signed S3 upload URL for medical registration certificates or degrees.
    """
    s3_key = f"doctors/{current_user.id}/credentials/{uuid.uuid4()}_{req.file_name}"
    upload_url = storage_service.generate_presigned_upload_url(
        bucket_name=settings.S3_BUCKET_DOCUMENTS,
        s3_key=s3_key,
        content_type=req.content_type
    )
    return DocumentPresignResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=3600
    )

@router.post("/documents/confirm", response_model=DoctorDocumentRead, status_code=status.HTTP_201_CREATED)
async def confirm_document_upload(
    req: DocumentConfirmRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db)
):
    """
    Registers the uploaded document metadata in the database against the doctor profile.
    """
    doc = DoctorDocument(
        id=uuid.uuid4(),
        doctor_id=current_user.id,
        doc_type=req.doc_type,
        file_name=req.file_name,
        s3_key=req.s3_key
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc

@router.get("/me", response_model=DoctorRead)
async def get_doctor_profile(
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(Doctor).where(Doctor.user_id == current_user.id)
    doctor = (await session.execute(stmt)).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    return doctor

@router.get("/me/documents", response_model=List[DoctorDocumentRead])
async def list_doctor_documents(
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(DoctorDocument).where(DoctorDocument.doctor_id == current_user.id)
    docs = (await session.execute(stmt)).scalars().all()
    return docs

@router.post("/me/toggle-listing", response_model=DoctorRead)
async def toggle_listing_online(
    req: DoctorVisibilityUpdate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db)
):
    """
    Toggles doctor listing online/offline.
    Enforces Hard Rule: Unverified doctors cannot be published online!
    """
    stmt = select(Doctor).where(Doctor.user_id == current_user.id)
    doctor = (await session.execute(stmt)).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")

    if req.listing_online is not None:
        if req.listing_online and doctor.verification_status != VerificationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor profile must be 'verified' before going online."
            )
        doctor.listing_online = req.listing_online

    if req.video_enabled is not None:
        if req.video_enabled and doctor.verification_status != VerificationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor profile must be 'verified' before offering video consultations."
            )
        doctor.video_enabled = req.video_enabled

    await session.commit()
    await session.refresh(doctor)

    # RUL-02: Broadcast toggle to Redis Pub/Sub for instant search index update
    try:
        await publish_event(
            "doctor:events",
            "doctor_visibility_toggled",
            {
                "doctor_id": str(doctor.user_id),
                "listing_online": doctor.listing_online,
                "video_enabled": doctor.video_enabled
            }
        )
    except Exception as e:
        print(f"[DOCTOR API] Warning: Redis publish failed: {e}")

    return doctor
