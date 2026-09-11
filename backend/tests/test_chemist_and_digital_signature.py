import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.chemists import (
    dispense_prescription,
    list_chemist_prescriptions,
    list_chemists,
    register_chemist,
    verify_prescription_signature_endpoint,
)
from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.chemist import Chemist
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.patient import Patient
from backend.app.models.prescription import Prescription
from backend.app.models.user import User, UserRole
from backend.app.schemas.chemist import ChemistRegisterRequest
from backend.app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
from backend.app.services.digital_signature import (
    generate_prescription_signature,
    verify_prescription_signature,
)
from backend.app.services.prescription_service import create_prescription


async def _create_test_entities(
    session: AsyncSession,
) -> tuple[User, Doctor, Clinic, User, Patient, User, Chemist]:
    """Helper to set up doctor, clinic, patient, and chemist users for testing."""
    # Doctor User & Profile
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    session.add(doc_user)
    await session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Priya Sharma",
        medical_reg_number=f"KMC-{uuid.uuid4().hex[:6].upper()}",
        council_name="Karnataka Medical Council",
        specialty="General Medicine",
        years_experience=12,
        in_person_fee=Decimal("600.00"),
    )
    clinic = Clinic(
        id=uuid.uuid4(),
        doctor_id=doc_user.id,
        name="Arogya Clinic Indiranagar",
        address="789 100 Feet Road",
        city="Bengaluru",
        locality="Indiranagar",
        pincode="560038",
        contact_number="+918025251122",
        latitude=Decimal("12.9716"),
        longitude=Decimal("77.5946"),
    )

    # Patient User & Profile
    pat_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    session.add(pat_user)
    await session.flush()

    patient = Patient(
        user_id=pat_user.id,
        full_name="Karan Verma",
        gender="male",
        date_of_birth=date(1990, 5, 20),
    )

    # Chemist User & Profile
    chem_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.CHEMIST,
        is_active=True,
    )
    session.add(chem_user)
    await session.flush()

    chemist = Chemist(
        id=uuid.uuid4(),
        user_id=chem_user.id,
        pharmacy_name="MedPlus Pharmacy Indiranagar",
        license_number=f"KA-BZ-DL-{uuid.uuid4().hex[:8].upper()}",
        clinic_id=clinic.id,
        address="Ground Floor, Arogya Clinic Complex",
        city="Bengaluru",
        locality="Indiranagar",
        pincode="560038",
        contact_number="+918025253344",
        is_active=True,
    )

    session.add_all((doctor, clinic, patient, chemist))
    await session.commit()
    await session.refresh(doctor)
    await session.refresh(clinic)
    await session.refresh(patient)
    await session.refresh(chemist)

    return doc_user, doctor, clinic, pat_user, patient, chem_user, chemist


async def _create_completed_appointment(
    session: AsyncSession,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
    clinic_id: uuid.UUID | None = None,
) -> Appointment:
    now = datetime.now(UTC)
    appointment = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.COMPLETED,
        slot_start=now - timedelta(minutes=45),
        slot_end=now - timedelta(minutes=30),
        fee_amount=Decimal("600.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@pytest.mark.asyncio
async def test_chemist_registration_and_listing(db_session: AsyncSession):
    """Verify chemist registration, unique constraints, and directory listing."""
    new_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9195{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(new_user)
    await db_session.commit()

    dl_num = f"KA-BLR-DL-{uuid.uuid4().hex[:6].upper()}"
    req = ChemistRegisterRequest(
        pharmacy_name="Guardian Pharmacy",
        license_number=dl_num,
        address="Shop 2, CMH Road",
        city="Bengaluru",
        locality="Indiranagar",
        pincode="560038",
        contact_number="+918025556677",
    )

    # 1. Register successfully
    chemist_res = await register_chemist(req, current_user=new_user, session=db_session)
    assert chemist_res.pharmacy_name == "Guardian Pharmacy"
    assert chemist_res.license_number == dl_num
    assert chemist_res.is_active is True

    # Check user role updated to CHEMIST
    await db_session.refresh(new_user)
    assert new_user.role == UserRole.CHEMIST

    # 2. Duplicate registration attempt by same user
    with pytest.raises(HTTPException) as exc:
        await register_chemist(req, current_user=new_user, session=db_session)
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail

    # 3. Directory listing with filters
    chemists = await list_chemists(city="Bengaluru", locality="Indiranagar", session=db_session)
    assert any(c.license_number == dl_num for c in chemists)


@pytest.mark.asyncio
async def test_doctor_issuing_signed_prescription_and_routing_to_chemist(
    db_session: AsyncSession,
):
    """Doctor issues digitally signed prescription and routes it to designated chemist."""
    doc_u, doctor, clinic, pat_u, patient, chem_u, chemist = await _create_test_entities(
        db_session
    )
    appointment = await _create_completed_appointment(
        db_session, doctor_id=doc_u.id, patient_id=pat_u.id, clinic_id=clinic.id
    )

    rx_payload = PrescriptionCreate(
        appointment_id=appointment.id,
        diagnosis="Acute Bronchitis and allergic rhinitis",
        clinical_notes="Hydration, steam inhalation, and 5-day course.",
        chemist_id=chemist.id,
        items=[
            PrescriptionItemCreate(
                drug_name="Amoxicillin + Clavulanic Acid 625mg",
                dosage="1 tablet",
                frequency="1-0-1 after food",
                duration_days=5,
                instructions="Finish the full course",
            ),
            PrescriptionItemCreate(
                drug_name="Cetirizine 10mg",
                dosage="1 tablet",
                frequency="0-0-1 at bedtime",
                duration_days=5,
                instructions="May cause mild drowsiness",
            ),
        ],
    )

    # Doctor issues prescription
    prescription = await create_prescription(
        doctor_id=doc_u.id,
        req=rx_payload,
        session=db_session,
    )

    # Verify signature and routing
    assert prescription.chemist_id == chemist.id
    assert prescription.digital_signature is not None
    assert len(prescription.digital_signature) == 64  # SHA-256 HMAC hex string
    assert prescription.dispense_status == "pending"
    assert prescription.dispensed_at is None

    # Chemist retrieves routed prescriptions
    routed_prescriptions = await list_chemist_prescriptions(
        dispense_status="pending",
        current_user=chem_u,
        session=db_session,
    )
    assert any(p.id == prescription.id for p in routed_prescriptions)


@pytest.mark.asyncio
async def test_cryptographic_signature_verification(db_session: AsyncSession):
    """Verify cryptographic signature integrity and anti-tampering guarantee."""
    doc_u, doctor, clinic, pat_u, patient, chem_u, chemist = await _create_test_entities(
        db_session
    )
    appointment = await _create_completed_appointment(
        db_session, doctor_id=doc_u.id, patient_id=pat_u.id, clinic_id=clinic.id
    )

    rx_payload = PrescriptionCreate(
        appointment_id=appointment.id,
        diagnosis="Hypertension Stage 1",
        clinical_notes="Low sodium diet and morning exercise.",
        chemist_id=chemist.id,
        items=[
            PrescriptionItemCreate(
                drug_name="Telmisartan 40mg",
                dosage="1 tablet",
                frequency="1-0-0 morning",
                duration_days=30,
                instructions="Empty stomach",
            )
        ],
    )
    prescription = await create_prescription(
        doctor_id=doc_u.id,
        req=rx_payload,
        session=db_session,
    )

    # Verify via endpoint
    verify_resp = await verify_prescription_signature_endpoint(
        prescription_id=prescription.id,
        session=db_session,
    )
    assert verify_resp.valid is True
    assert verify_resp.doctor_reg_number == doctor.medical_reg_number
    assert verify_resp.digital_signature == prescription.digital_signature

    # Verify via digital signature service
    rx_model = await db_session.get(Prescription, prescription.id)
    is_valid = verify_prescription_signature(
        prescription=rx_model,
        medical_reg_number=doctor.medical_reg_number,
    )
    assert is_valid is True

    # Test tampering detection: alter signature
    rx_model.digital_signature = "a" * 64
    assert (
        verify_prescription_signature(
            prescription=rx_model,
            medical_reg_number=doctor.medical_reg_number,
        )
        is False
    )


@pytest.mark.asyncio
async def test_chemist_dispensing_prescription(db_session: AsyncSession):
    """Chemist dispenses prescription, preventing duplicate dispensing and cross-chemist access."""
    doc_u, doctor, clinic, pat_u, patient, chem_u, chemist = await _create_test_entities(
        db_session
    )
    appointment = await _create_completed_appointment(
        db_session, doctor_id=doc_u.id, patient_id=pat_u.id, clinic_id=clinic.id
    )

    rx_payload = PrescriptionCreate(
        appointment_id=appointment.id,
        diagnosis="Gastritis",
        clinical_notes="Avoid spicy food.",
        chemist_id=chemist.id,
        items=[
            PrescriptionItemCreate(
                drug_name="Pantoprazole 40mg",
                dosage="1 capsule",
                frequency="1-0-0 before breakfast",
                duration_days=14,
                instructions="Take with warm water",
            )
        ],
    )
    prescription = await create_prescription(
        doctor_id=doc_u.id,
        req=rx_payload,
        session=db_session,
    )

    # 1. Other chemist tries to dispense routed prescription -> 403 Forbidden
    other_chem_u = User(
        id=uuid.uuid4(),
        phone_number=f"+9194{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.CHEMIST,
        is_active=True,
    )
    db_session.add(other_chem_u)
    await db_session.flush()

    other_chemist = Chemist(
        id=uuid.uuid4(),
        user_id=other_chem_u.id,
        pharmacy_name="Other Pharma",
        license_number=f"DL-OTH-{uuid.uuid4().hex[:6]}",
        address="Other St",
        city="Bengaluru",
        locality="Koramangala",
        pincode="560034",
        contact_number="+918099887766",
        is_active=True,
    )
    db_session.add(other_chemist)
    await db_session.commit()

    with pytest.raises(HTTPException) as forbidden_exc:
        await dispense_prescription(
            prescription_id=prescription.id,
            current_user=other_chem_u,
            session=db_session,
        )
    assert forbidden_exc.value.status_code == 403

    # 2. Correct chemist dispenses successfully
    dispense_res = await dispense_prescription(
        prescription_id=prescription.id,
        current_user=chem_u,
        session=db_session,
    )
    assert dispense_res.dispense_status == "dispensed"
    assert dispense_res.dispensed_at is not None
    assert dispense_res.dispensed_by_chemist_id == chemist.id

    # 3. Repeat dispense attempt -> 400 Bad Request
    with pytest.raises(HTTPException) as repeat_exc:
        await dispense_prescription(
            prescription_id=prescription.id,
            current_user=chem_u,
            session=db_session,
        )
    assert repeat_exc.value.status_code == 400
    assert "already dispensed" in repeat_exc.value.detail
