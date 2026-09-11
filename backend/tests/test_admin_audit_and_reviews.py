"""Phase 08 test coverage: RBAC, reviews, moderation, audit logging (RUL-04), and reminder dispatch."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_super_admin, require_verification_reviewer
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.api.v1.admin_moderation import list_chemists_for_moderation, update_chemist_status
from backend.app.models.appointment import Appointment, AppointmentMode, AppointmentStatus, PaymentStatus
from backend.app.models.audit import AuditLog
from backend.app.models.chemist import Chemist
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.notification import Notification, NotificationStatus, NotificationType
from backend.app.models.patient_document import PatientDocument
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.models.review import Review, ReviewStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.admin import ChemistStatusUpdateAction
from backend.app.schemas.review import ReviewCreate
from backend.app.services.admin_analytics import get_platform_telemetry
from backend.app.services.reminder_service import dispatch_upcoming_reminders
from backend.app.services.review_service import moderate_review, submit_review


async def _review_fixture(session: AsyncSession, status=AppointmentStatus.COMPLETED):
    patient = User(
        id=uuid.uuid4(),
        phone_number=f"+9191{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    doctor_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9192{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    admin = User(
        id=uuid.uuid4(),
        phone_number=f"+9193{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        phone_number=f"+9194{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.VERIFICATION_REVIEWER,
        is_active=True,
    )
    session.add_all((patient, doctor_user, admin, reviewer))
    await session.flush()

    doctor = Doctor(
        user_id=doctor_user.id,
        full_name="Dr Review",
        medical_reg_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        council_name="State Medical Council",
        specialty="Cardiology",
        years_experience=10,
        verification_status=VerificationStatus.VERIFIED,
    )
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.user_id,
        mode=AppointmentMode.VIDEO,
        status=status,
        slot_start=datetime.now(timezone.utc) + timedelta(minutes=30),
        slot_end=datetime.now(timezone.utc) + timedelta(hours=1),
        fee_amount=Decimal("500.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add_all((doctor, appt))
    await session.commit()
    return patient, doctor, admin, reviewer, appt


@pytest.mark.asyncio
async def test_rbac_telemetry_access(db_session: AsyncSession):
    """
    ADM-02: Reviewer role is blocked from dashboard telemetry (HTTP 403); super_admin permitted.
    """
    patient, doctor, admin, reviewer, appt = await _review_fixture(db_session)

    # 1. Super admin is permitted to access telemetry
    allowed_admin = await require_super_admin(admin)
    assert allowed_admin.id == admin.id

    # 2. Verification reviewer is blocked from telemetry with 403
    with pytest.raises(HTTPException) as exc_info:
        await require_super_admin(reviewer)
    assert exc_info.value.status_code == 403
    assert "Operation not permitted" in exc_info.value.detail

    # 3. Patient and Doctor are blocked from telemetry with 403
    with pytest.raises(HTTPException) as exc_patient:
        await require_super_admin(patient)
    assert exc_patient.value.status_code == 403

    # 4. require_verification_reviewer permits both reviewer and super_admin
    assert (await require_verification_reviewer(reviewer)).id == reviewer.id
    assert (await require_verification_reviewer(admin)).id == admin.id

    # 5. Telemetry calculates metrics accurately
    telemetry = await get_platform_telemetry(db_session)
    assert telemetry.total_verified_doctors >= 1
    assert telemetry.total_confirmed_bookings >= 1
    assert telemetry.total_completed_consultations >= 1
    assert telemetry.gross_transaction_value >= Decimal("500.00")


@pytest.mark.asyncio
async def test_review_submission_only_on_completed(db_session: AsyncSession):
    """
    PAT-05: Patient can submit exactly one review for a completed appointment.
    """
    patient, doctor, _, _, appt = await _review_fixture(db_session, AppointmentStatus.CONFIRMED)

    # 1. Reject review for uncompleted appointment
    with pytest.raises(HTTPException) as error:
        await submit_review(patient.id, ReviewCreate(appointment_id=appt.id, rating=5, review_text="Great doc!"), db_session)
    assert error.value.status_code == 400

    # 2. Complete appointment and submit review
    appt.status = AppointmentStatus.COMPLETED
    await db_session.commit()

    review = await submit_review(
        patient.id,
        ReviewCreate(appointment_id=appt.id, rating=5, review_text="Excellent consultation!"),
        db_session
    )
    await db_session.refresh(doctor)
    assert review.status == ReviewStatus.PUBLISHED
    assert doctor.review_count == 1
    assert doctor.average_rating == Decimal("5.00")

    # 3. Duplicate review attempt rejected with 409 Conflict
    with pytest.raises(HTTPException) as duplicate:
        await submit_review(patient.id, ReviewCreate(appointment_id=appt.id, rating=4), db_session)
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_review_moderation_writes_audit_log(db_session: AsyncSession):
    """
    ADM-04, RUL-04: Admin hiding or removing a review creates immutable audit log record
    and adjusts doctor aggregate rating.
    """
    patient, doctor, admin, _, appt = await _review_fixture(db_session)
    review = await submit_review(
        patient.id,
        ReviewCreate(appointment_id=appt.id, rating=4, review_text="Good service"),
        db_session
    )
    await db_session.refresh(doctor)
    assert doctor.review_count == 1
    assert doctor.average_rating == Decimal("4.00")

    # 1. Admin hides review with mandatory reason
    hidden = await moderate_review(admin.id, review.id, "hide", "Inappropriate language in review", db_session)
    assert hidden.status == ReviewStatus.HIDDEN

    # 2. Verify immutable audit log record created
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.target_entity_type == "review",
                AuditLog.target_entity_id == review.id,
            )
        )
    ).scalar_one()
    assert audit.admin_user_id == admin.id
    assert audit.action == "review_hide"
    assert audit.reason == "Inappropriate language in review"
    assert audit.previous_state == {"status": "published"}
    assert audit.new_state == {"status": "hidden"}

    # 3. Doctor's aggregate rating excludes hidden review
    await db_session.refresh(doctor)
    assert doctor.review_count == 0
    assert doctor.average_rating == Decimal("0.00")

    # 4. Admin approves review back
    approved = await moderate_review(admin.id, review.id, "approve", "Appeal accepted upon review", db_session)
    assert approved.status == ReviewStatus.PUBLISHED
    await db_session.refresh(doctor)
    assert doctor.review_count == 1
    assert doctor.average_rating == Decimal("4.00")


@pytest.mark.asyncio
async def test_appointment_reminder_dispatch(db_session: AsyncSession):
    """
    PAT-07: Pre-appointment reminder dispatches automatically before scheduled slot
    and dispatches exactly once.
    """
    _, _, _, _, appt = await _review_fixture(db_session, AppointmentStatus.CONFIRMED)
    appt.reminder_sent = False
    await db_session.commit()

    # 1. Dispatch reminders
    created = await dispatch_upcoming_reminders(db_session)
    await db_session.refresh(appt)

    assert any(note.appointment_id == appt.id for note in created)
    assert appt.reminder_sent is True

    # Check notification in DB
    note = (
        await db_session.execute(
            select(Notification).where(Notification.appointment_id == appt.id)
        )
    ).scalar_one()
    assert note.type == NotificationType.APPOINTMENT_REMINDER
    assert note.status == NotificationStatus.SENT

    # 2. Subsequent call dispatches nothing for this appointment (idempotent / exactly once)
    second_run = await dispatch_upcoming_reminders(db_session)
    assert not any(n.appointment_id == appt.id for n in second_run)
    appt_notifications = (
        await db_session.execute(
            select(Notification).where(Notification.appointment_id == appt.id)
        )
    ).scalars().all()
    assert len(appt_notifications) == 1


@pytest.mark.asyncio
async def test_appointment_reminder_dispatch_for_requested_status(db_session: AsyncSession):
    """
    Verify dispatch_upcoming_reminders selects and dispatches notifications for
    both CONFIRMED and REQUESTED appointments within the reminder window.
    """
    _, _, _, _, appt = await _review_fixture(db_session, AppointmentStatus.REQUESTED)
    appt.reminder_sent = False
    await db_session.commit()

    created = await dispatch_upcoming_reminders(db_session)
    await db_session.refresh(appt)

    assert any(note.appointment_id == appt.id for note in created)
    assert appt.reminder_sent is True

    note = (
        await db_session.execute(
            select(Notification).where(Notification.appointment_id == appt.id)
        )
    ).scalar_one()
    assert note.type == NotificationType.APPOINTMENT_REMINDER
    assert note.channel.value in ("sms", "email")
    assert note.status == NotificationStatus.SENT



@pytest.mark.asyncio
async def test_reminder_dispatch_via_admin_api(db_session: AsyncSession):
    """
    Test reminder dispatch via admin API:
    - Create an upcoming confirmed appointment with reminder_sent=False.
    - Call POST /api/v1/admin/dashboard/dispatch-reminders as super_admin.
    - Verify response contains dispatched_count >= 1.
    - Verify appointment in DB now has reminder_sent == True.
    - Verify second invocation dispatches 0 (idempotent, single reminder guarantee PAT-05).
    - Verify non-super_admin receives 403 Forbidden.
    """
    patient, doctor, admin, reviewer, appt = await _review_fixture(db_session, AppointmentStatus.CONFIRMED)
    appt.reminder_sent = False
    await db_session.commit()

    admin_token = create_access_token(str(admin.id), role=admin.role.value)
    reviewer_token = create_access_token(str(reviewer.id), role=reviewer.role.value)
    patient_token = create_access_token(str(patient.id), role=patient.role.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Non-super_admin receives 403 Forbidden
        resp_reviewer = await client.post(
            "/api/v1/admin/dashboard/dispatch-reminders",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp_reviewer.status_code == 403

        resp_patient = await client.post(
            "/api/v1/admin/dashboard/dispatch-reminders",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert resp_patient.status_code == 403

        # 2. super_admin calls endpoint
        resp = await client.post(
            "/api/v1/admin/dashboard/dispatch-reminders",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dispatched_count"] >= 1
        assert "timestamp" in data

        # 3. Verify appointment in DB now has reminder_sent == True
        await db_session.refresh(appt)
        assert appt.reminder_sent is True

        # 4. Second invocation dispatches 0 (idempotent, single reminder guarantee PAT-05)
        resp2 = await client.post(
            "/api/v1/admin/dashboard/dispatch-reminders",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["dispatched_count"] == 0



@pytest.mark.asyncio
async def test_admin_chemist_oversight_and_audit_logging(db_session: AsyncSession):
    """
    RUL-04 & ADM chemist moderation:
    Admin/Reviewer can list all registered pharmacies with DL numbers and statuses,
    toggle or update their status, and each status change writes an immutable audit log record
    with diff and mandatory reason within the same transaction.
    """
    # 1. Setup Admin, Reviewer, Chemist, and Patient
    admin = User(
        id=uuid.uuid4(),
        phone_number=f"+9193{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        phone_number=f"+9194{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.VERIFICATION_REVIEWER,
        is_active=True,
    )
    chemist_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9195{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.CHEMIST,
        is_active=True,
    )
    patient_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add_all((admin, reviewer, chemist_user, patient_user))
    await db_session.flush()

    dl_number = f"DL-{uuid.uuid4().hex[:8].upper()}"
    chemist = Chemist(
        id=uuid.uuid4(),
        user_id=chemist_user.id,
        pharmacy_name="MedLife Care Pharmacy",
        license_number=dl_number,
        clinic_id=None,
        address="10 Central Avenue",
        city="Pune",
        locality="Kothrud",
        pincode="411038",
        contact_number="+919876543210",
        is_active=True,
    )
    doc = PatientDocument(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        doc_type="lab_report",
        file_name="blood_test.pdf",
        s3_key="documents/blood_test.pdf",
        file_size_bytes=1024,
    )
    db_session.add_all((chemist, doc))
    await db_session.commit()

    # 2. RBAC check: Patient is rejected with 403
    with pytest.raises(HTTPException) as rbac_exc:
        await require_verification_reviewer(patient_user)
    assert rbac_exc.value.status_code == 403

    # Reviewer and Super Admin are permitted
    assert (await require_verification_reviewer(reviewer)).id == reviewer.id
    assert (await require_verification_reviewer(admin)).id == admin.id

    # 3. List chemists for moderation (verifying DL, pharmacy name, active status)
    chemists_list = await list_chemists_for_moderation(current_user=admin, session=db_session)
    found_chemist = next((c for c in chemists_list if c.id == chemist.id), None)
    assert found_chemist is not None
    assert found_chemist.pharmacy_name == "MedLife Care Pharmacy"
    assert found_chemist.license_number == dl_number
    assert found_chemist.is_active is True

    # 4. Suspend chemist with mandatory reason
    suspend_action = ChemistStatusUpdateAction(
        action="suspend",
        reason_text="Drug license under investigation by State Pharmacy Council",
    )
    updated_chemist = await update_chemist_status(
        chemist_id=chemist.id,
        payload=suspend_action,
        current_user=admin,
        session=db_session,
    )
    assert updated_chemist.is_active is False

    # 5. Verify immutable audit log record created in same transaction (RUL-04)
    audit_entry = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.target_entity_type == "chemist",
                AuditLog.target_entity_id == chemist.id,
                AuditLog.action == "chemist_suspend",
            )
        )
    ).scalar_one()
    assert audit_entry.admin_user_id == admin.id
    assert audit_entry.reason == "Drug license under investigation by State Pharmacy Council"
    assert audit_entry.previous_state["status"] == "active"
    assert audit_entry.previous_state["is_active"] is True
    assert audit_entry.new_state["status"] == "suspended"
    assert audit_entry.new_state["is_active"] is False

    # 6. Reactivate chemist with reviewer role
    activate_action = ChemistStatusUpdateAction(
        action="activate",
        reason_text="Drug license clearance certificate received and verified",
    )
    reactivated_chemist = await update_chemist_status(
        chemist_id=chemist.id,
        payload=activate_action,
        current_user=reviewer,
        session=db_session,
    )
    assert reactivated_chemist.is_active is True

    # Verify second audit log entry
    audits = (
        await db_session.execute(
            select(AuditLog)
            .where(
                AuditLog.target_entity_type == "chemist",
                AuditLog.target_entity_id == chemist.id,
            )
            .order_by(AuditLog.created_at.asc())
        )
    ).scalars().all()
    assert len(audits) == 2
    assert audits[1].admin_user_id == reviewer.id
    assert audits[1].action == "chemist_activate"
    assert audits[1].reason == "Drug license clearance certificate received and verified"
    assert audits[1].previous_state["is_active"] is False
    assert audits[1].new_state["is_active"] is True

    # 7. Validation error handling
    # Empty reason
    with pytest.raises(HTTPException) as empty_reason_exc:
        await update_chemist_status(
            chemist_id=chemist.id,
            payload=ChemistStatusUpdateAction(action="suspend", reason_text="   "),
            current_user=admin,
            session=db_session,
        )
    assert empty_reason_exc.value.status_code == 400

    # Unsupported action
    with pytest.raises(HTTPException) as invalid_action_exc:
        await update_chemist_status(
            chemist_id=chemist.id,
            payload=ChemistStatusUpdateAction(action="delete", reason_text="Invalid action"),
            current_user=admin,
            session=db_session,
        )
    assert invalid_action_exc.value.status_code == 400

    # Non-existent chemist
    with pytest.raises(HTTPException) as not_found_exc:
        await update_chemist_status(
            chemist_id=uuid.uuid4(),
            payload=ChemistStatusUpdateAction(action="suspend", reason_text="Valid reason"),
            current_user=admin,
            session=db_session,
        )
    assert not_found_exc.value.status_code == 404

    # 8. Verify Platform Telemetry includes registered chemists and patient documents
    telemetry = await get_platform_telemetry(db_session)
    assert telemetry.total_registered_chemists >= 1
    assert telemetry.total_patient_documents >= 1

