import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.audit import AuditLog
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.user import User, UserRole
from backend.app.models.verification import DocumentType, DoctorDocument, VerificationReview
from backend.app.services.storage import storage_service
from backend.app.services.verification_state import (
    InvalidVerificationTransitionError,
    verification_state_machine,
)

@pytest.fixture
def sample_doctor_user():
    return User(
        id=uuid.uuid4(),
        phone_number=f"+9191{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True
    )

@pytest.fixture
def sample_reviewer_user():
    return User(
        id=uuid.uuid4(),
        phone_number=f"+9192{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.VERIFICATION_REVIEWER,
        is_active=True
    )

@pytest.mark.asyncio
async def test_doctor_onboarding_and_document_linking(
    db_session: AsyncSession,
    sample_doctor_user: User
):
    # 1. Register User & Doctor profile
    db_session.add(sample_doctor_user)
    await db_session.commit()

    doctor = Doctor(
        user_id=sample_doctor_user.id,
        full_name="Dr. Rajesh Sharma",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Delhi Medical Council",
        specialty="General Medicine",
        years_experience=12,
        bio="Senior consultant with over 12 years of clinical OPD experience.",
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False
    )
    db_session.add(doctor)
    await db_session.commit()
    await db_session.refresh(doctor)

    assert doctor.verification_status == VerificationStatus.SUBMITTED
    assert doctor.listing_online is False

    # 2. Upload Document metadata
    doc1 = DoctorDocument(
        id=uuid.uuid4(),
        doctor_id=doctor.user_id,
        doc_type=DocumentType.MEDICAL_REG_CERT,
        file_name="mci_registration.pdf",
        s3_key=f"doctors/{doctor.user_id}/credentials/mci_reg.pdf"
    )
    doc2 = DoctorDocument(
        id=uuid.uuid4(),
        doctor_id=doctor.user_id,
        doc_type=DocumentType.DEGREE_CERT,
        file_name="mbbs_degree.pdf",
        s3_key=f"doctors/{doctor.user_id}/credentials/mbbs_degree.pdf"
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    # Verify query with documents
    await db_session.refresh(doctor, ["documents"])
    assert len(doctor.documents) == 2

@pytest.mark.asyncio
async def test_presigned_s3_url_generation():
    key = f"doctors/{uuid.uuid4()}/credentials/test_cert.pdf"
    upload_url = storage_service.generate_presigned_upload_url(
        bucket_name="doctor-documents",
        s3_key=key,
        content_type="application/pdf"
    )
    assert upload_url is not None
    assert "doctor-documents" in upload_url
    assert "X-Amz-Signature" in upload_url

    download_url = storage_service.generate_presigned_download_url(
        bucket_name="doctor-documents",
        s3_key=key
    )
    assert download_url is not None
    assert "X-Amz-Signature" in download_url

@pytest.mark.asyncio
async def test_full_6_state_verification_pipeline_with_immutable_audit(
    db_session: AsyncSession,
    sample_doctor_user: User,
    sample_reviewer_user: User
):
    """
    Validates complete 6-state pipeline (PRD 2D) and RUL-04 (immutable audit logging).
    """
    db_session.add_all([sample_doctor_user, sample_reviewer_user])
    await db_session.commit()

    doctor = Doctor(
        user_id=sample_doctor_user.id,
        full_name="Dr. Ananya Roy",
        medical_reg_number=f"KMC-{uuid.uuid4().hex[:8].upper()}",
        council_name="Karnataka Medical Council",
        specialty="Dermatology",
        years_experience=8,
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False
    )
    db_session.add(doctor)
    await db_session.commit()

    admin_id = sample_reviewer_user.id

    # 1. Submitted -> UnderReview
    review1 = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.UNDER_REVIEW,
        admin_user_id=admin_id,
        session=db_session,
        reason_text="Assigned reviewer claiming verification task."
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.UNDER_REVIEW
    assert review1.previous_status == VerificationStatus.SUBMITTED
    assert review1.new_status == VerificationStatus.UNDER_REVIEW

    # 2. UnderReview -> InfoRequested
    review2 = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.INFO_REQUESTED,
        admin_user_id=admin_id,
        session=db_session,
        reason_text="Uploaded degree certificate is blurry, re-upload required.",
        review_notes="Requested high-resolution scan."
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.INFO_REQUESTED

    # 3. InfoRequested -> UnderReview (doctor re-submitted info)
    review3 = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.UNDER_REVIEW,
        admin_user_id=admin_id,
        session=db_session,
        reason_text="Doctor submitted new high-res certificate."
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.UNDER_REVIEW

    # 4. UnderReview -> Verified
    review4 = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.VERIFIED,
        admin_user_id=admin_id,
        session=db_session,
        reason_text="Credentials verified against council registry records."
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.VERIFIED

    # Doctor can now toggle listing online
    doctor.listing_online = True
    doctor.video_enabled = True
    await db_session.commit()
    assert doctor.listing_online is True

    # 5. Verified -> Suspended (e.g. Trust & Safety incident)
    suspension_reason = "Patient complaint regarding medical council discrepancy pending investigation."
    review5 = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.SUSPENDED,
        admin_user_id=admin_id,
        session=db_session,
        reason_text=suspension_reason
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.SUSPENDED
    # Must be forced offline automatically when suspended
    assert doctor.listing_online is False
    assert doctor.video_enabled is False

    # 6. Suspended -> Verified (cleared of investigation)
    review6 = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.VERIFIED,
        admin_user_id=admin_id,
        session=db_session,
        reason_text="Investigation cleared; council certificate confirmed genuine."
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.VERIFIED

    # Verify RUL-04: Immutable Audit Logging
    stmt = select(AuditLog).where(
        AuditLog.target_entity_type == "doctor",
        AuditLog.target_entity_id == doctor.user_id
    ).order_by(AuditLog.created_at.asc())
    audit_rows = (await db_session.execute(stmt)).scalars().all()

    # All 6 transitions must have written distinct immutable audit records
    assert len(audit_rows) == 6
    assert audit_rows[0].action == "doctor_verification_under_review"
    assert audit_rows[3].action == "doctor_verification_verified"
    assert audit_rows[4].action == "doctor_verification_suspended"
    assert audit_rows[4].reason == suspension_reason
    assert audit_rows[4].previous_state == {"status": "verified"}
    assert audit_rows[4].new_state == {"status": "suspended"}

@pytest.mark.asyncio
async def test_rejection_requires_mandatory_reason(
    db_session: AsyncSession,
    sample_doctor_user: User,
    sample_reviewer_user: User
):
    db_session.add_all([sample_doctor_user, sample_reviewer_user])
    await db_session.commit()

    doctor = Doctor(
        user_id=sample_doctor_user.id,
        full_name="Dr. Fraudulent Applicant",
        medical_reg_number=f"BAD-{uuid.uuid4().hex[:8].upper()}",
        council_name="Bogus Council",
        specialty="Cardiology",
        verification_status=VerificationStatus.UNDER_REVIEW,
        listing_online=False
    )
    db_session.add(doctor)
    await db_session.commit()

    # Rejection without reason MUST raise HTTP 422
    with pytest.raises(HTTPException) as exc_info:
        await verification_state_machine.transition_doctor_status(
            doctor=doctor,
            new_status=VerificationStatus.REJECTED,
            admin_user_id=sample_reviewer_user.id,
            session=db_session,
            reason_text=""  # Empty reason!
        )
    assert exc_info.value.status_code == 422
    assert "requires a non-empty reason" in exc_info.value.detail

    # Rejection with reason succeeds
    review = await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.REJECTED,
        admin_user_id=sample_reviewer_user.id,
        session=db_session,
        reason_text="Fraudulent diploma detected."
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.REJECTED

@pytest.mark.asyncio
async def test_unverified_doctor_cannot_go_online(
    db_session: AsyncSession,
    sample_doctor_user: User
):
    db_session.add(sample_doctor_user)
    await db_session.commit()

    doctor = Doctor(
        user_id=sample_doctor_user.id,
        full_name="Dr. Pending Verification",
        medical_reg_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        council_name="State Council",
        specialty="Pediatrics",
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False
    )
    db_session.add(doctor)
    await db_session.commit()

    # Verify model default
    assert doctor.listing_online is False

@pytest.mark.asyncio
async def test_illegal_verification_transition_raises_422(
    db_session: AsyncSession,
    sample_doctor_user: User,
    sample_reviewer_user: User
):
    db_session.add_all([sample_doctor_user, sample_reviewer_user])
    await db_session.commit()

    doctor = Doctor(
        user_id=sample_doctor_user.id,
        full_name="Dr. Leap Applicant",
        medical_reg_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        council_name="State Council",
        specialty="Pediatrics",
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False
    )
    db_session.add(doctor)
    await db_session.commit()

    # Direct illegal leap: Submitted -> Verified (skipping UnderReview)
    with pytest.raises(InvalidVerificationTransitionError):
        await verification_state_machine.transition_doctor_status(
            doctor=doctor,
            new_status=VerificationStatus.VERIFIED,
            admin_user_id=sample_reviewer_user.id,
            session=db_session,
            reason_text="Trying to shortcut review."
        )
