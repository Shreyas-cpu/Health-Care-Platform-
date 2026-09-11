import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.patient_vault import (
    get_appointment_history,
    get_patient_vault,
    upload_patient_document,
)
from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.patient import Patient
from backend.app.models.user import User, UserRole
from backend.app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
from backend.app.services.prescription_service import create_prescription


async def _setup_patient(session: AsyncSession) -> tuple[User, Patient]:
    pat_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9193{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    session.add(pat_user)
    await session.flush()

    patient = Patient(
        user_id=pat_user.id,
        full_name="Vikram Sethi",
        gender="male",
        date_of_birth=date(1988, 7, 14),
    )
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return pat_user, patient


async def _setup_doctor_and_clinic(
    session: AsyncSession,
    lat: Decimal | None = Decimal("19.0760"),
    lng: Decimal | None = Decimal("72.8777"),
) -> tuple[User, Doctor, Clinic]:
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9192{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    session.add(doc_user)
    await session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Sunita Deshmukh",
        medical_reg_number=f"MMC-{uuid.uuid4().hex[:6].upper()}",
        council_name="Maharashtra Medical Council",
        specialty="Cardiology",
        years_experience=15,
        in_person_fee=Decimal("800.00"),
    )
    clinic = Clinic(
        id=uuid.uuid4(),
        doctor_id=doc_user.id,
        name="Heart & Health Clinic",
        address="Flat 101, Sea View Residency, Prabhadevi",
        city="Mumbai",
        locality="Prabhadevi",
        pincode="400025",
        contact_number="+912224301122",
        latitude=lat,
        longitude=lng,
    )
    session.add_all((doctor, clinic))
    await session.commit()
    await session.refresh(doctor)
    await session.refresh(clinic)
    return doc_user, doctor, clinic


@pytest.mark.asyncio
async def test_patient_document_upload_and_listing(db_session: AsyncSession):
    """Test patient health document upload, storage, and unified vault retrieval."""
    pat_user, _ = await _setup_patient(db_session)

    # 1. Upload health documents
    dummy_pdf_bytes = b"%PDF-1.4 Mock Lab Report Content for CBC and Lipid Profile"
    upload_file = UploadFile(
        file=io.BytesIO(dummy_pdf_bytes),
        filename="blood_report_sept2026.pdf",
        headers={"content-type": "application/pdf"},
    )

    upload_resp = await upload_patient_document(
        file=upload_file,
        doc_type="lab_report",
        notes="Annual preventive lipid panel and CBC",
        current_user=pat_user,
        session=db_session,
    )

    assert upload_resp.patient_id == pat_user.id
    assert upload_resp.doc_type == "lab_report"
    assert upload_resp.file_name == "blood_report_sept2026.pdf"
    assert upload_resp.file_size_bytes == len(dummy_pdf_bytes)
    assert upload_resp.download_url is not None
    assert "patient-documents" in upload_resp.download_url or upload_resp.id.hex in upload_resp.download_url

    # 2. Query patient vault (uploaded documents only)
    vault_resp = await get_patient_vault(
        current_user=pat_user,
        session=db_session,
    )
    assert len(vault_resp.uploaded_documents) >= 1
    uploaded_item = next(item for item in vault_resp.uploaded_documents if item.id == upload_resp.id)
    assert uploaded_item.doc_type == "lab_report"
    assert uploaded_item.file_name == "blood_report_sept2026.pdf"

    # 3. Create appointment and issue prescription for the patient
    doc_user, doctor, clinic = await _setup_doctor_and_clinic(db_session)
    now = datetime.now(UTC)
    appointment = Appointment(
        id=uuid.uuid4(),
        patient_id=pat_user.id,
        doctor_id=doc_user.id,
        clinic_id=clinic.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.COMPLETED,
        slot_start=now - timedelta(hours=2),
        slot_end=now - timedelta(hours=1, minutes=30),
        fee_amount=Decimal("800.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    db_session.add(appointment)
    await db_session.commit()

    rx_payload = PrescriptionCreate(
        appointment_id=appointment.id,
        diagnosis="Hyperlipidemia",
        clinical_notes="Low fat diet, follow up in 3 months.",
        items=[
            PrescriptionItemCreate(
                drug_name="Atorvastatin 10mg",
                dosage="1 tab",
                frequency="0-0-1 bedtime",
                duration_days=90,
                instructions="After dinner",
            )
        ],
    )
    prescription = await create_prescription(
        doctor_id=doc_user.id,
        req=rx_payload,
        session=db_session,
    )

    # 4. Query patient vault again -> must return uploaded documents AND prescriptions
    unified_vault = await get_patient_vault(
        current_user=pat_user,
        session=db_session,
    )
    assert len(unified_vault.uploaded_documents) >= 1
    assert len(unified_vault.prescriptions) >= 1

    rx_item = next(item for item in unified_vault.prescriptions if item.id == prescription.id)
    assert rx_item.diagnosis == "Hyperlipidemia"


@pytest.mark.asyncio
async def test_appointment_history_with_clinic_google_maps_url(db_session: AsyncSession):
    """Test appointment history with complete clinical details and Google Maps URL navigation."""
    pat_user, _ = await _setup_patient(db_session)

    # 1. Doctor with coordinates
    doc_user1, doc1, clinic1 = await _setup_doctor_and_clinic(
        db_session,
        lat=Decimal("19.0178"),
        lng=Decimal("72.8300"),
    )
    now = datetime.now(UTC)
    appt1 = Appointment(
        id=uuid.uuid4(),
        patient_id=pat_user.id,
        doctor_id=doc_user1.id,
        clinic_id=clinic1.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.COMPLETED,
        slot_start=now - timedelta(days=2),
        slot_end=now - timedelta(days=2, minutes=-30),
        fee_amount=Decimal("800.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    db_session.add(appt1)
    await db_session.commit()

    # Add prescription to appt1
    rx_payload = PrescriptionCreate(
        appointment_id=appt1.id,
        diagnosis="Normal ECG routine check",
        clinical_notes="All clear.",
        items=[
            PrescriptionItemCreate(
                drug_name="Multivitamin",
                dosage="1 tab",
                frequency="1-0-0 morning",
                duration_days=30,
            )
        ],
    )
    rx1 = await create_prescription(
        doctor_id=doc_user1.id,
        req=rx_payload,
        session=db_session,
    )

    # 2. Doctor without coordinates (fallback query URL)
    doc_user2, doc2, clinic2 = await _setup_doctor_and_clinic(
        db_session,
        lat=None,
        lng=None,
    )
    clinic2.name = "Suburban Care Center"
    clinic2.address = "SV Road, Bandra"
    clinic2.city = "Mumbai"
    clinic2.pincode = "400050"
    db_session.add(clinic2)
    await db_session.commit()

    appt2 = Appointment(
        id=uuid.uuid4(),
        patient_id=pat_user.id,
        doctor_id=doc_user2.id,
        clinic_id=clinic2.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.REQUESTED,
        slot_start=now + timedelta(days=1),
        slot_end=now + timedelta(days=1, minutes=30),
        fee_amount=Decimal("800.00"),
        payment_status=PaymentStatus.PENDING,
    )
    db_session.add(appt2)
    await db_session.commit()

    # 3. Retrieve history
    history = await get_appointment_history(
        current_user=pat_user,
        session=db_session,
    )

    assert len(history) >= 2
    item1 = next(h for h in history if h.appointment_id == appt1.id)
    assert item1.doctor_name == "Dr. Sunita Deshmukh"
    assert item1.specialty == "Cardiology"
    assert item1.clinic_name == "Heart & Health Clinic"
    assert item1.prescription_id == rx1.id
    assert item1.status == "completed"
    # Verify coordinate-based Google Maps URL
    assert "https://www.google.com/maps/search/?api=1&query=" in item1.google_maps_url
    assert "19.0178" in item1.google_maps_url
    assert "72.8300" in item1.google_maps_url

    item2 = next(h for h in history if h.appointment_id == appt2.id)
    assert item2.status == "requested"
    assert item2.prescription_id is None
    # Verify text fallback Google Maps URL
    assert "https://www.google.com/maps/search/?api=1&query=" in item2.google_maps_url
    assert "Suburban" in item2.google_maps_url or "Mumbai" in item2.google_maps_url
