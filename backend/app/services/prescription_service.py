"""Prescription authoring with CMP-01 telemedicine restricted-drug gating."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.app.core.config import settings
from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
)
from backend.app.models.doctor import Doctor
from backend.app.models.drug import DrugMaster, seed_default_drugs
from backend.app.models.prescription import Prescription, PrescriptionItem
from backend.app.schemas.prescription import (
    DrugMasterResponse,
    PrescriptionCreate,
    PrescriptionResponse,
)
from backend.app.services.digital_signature import generate_prescription_signature
from backend.app.services.pdf_compiler import compile_and_upload_prescription_pdf
from backend.app.services.storage import storage_service
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def _find_restricted_drug(
    drug_name: str,
    session: AsyncSession,
) -> DrugMaster | None:
    """Match DrugMaster by brand or generic name (case-insensitive exact)."""
    stmt = select(DrugMaster).where(
        or_(
            DrugMaster.brand_name.ilike(drug_name),
            DrugMaster.generic_name.ilike(drug_name),
        )
    )
    result = await session.execute(stmt)
    return result.scalars().first()


def _to_prescription_response(
    prescription: Prescription,
    download_url: str | None = None,
) -> PrescriptionResponse:
    return PrescriptionResponse(
        id=prescription.id,
        appointment_id=prescription.appointment_id,
        doctor_id=prescription.doctor_id,
        patient_id=prescription.patient_id,
        diagnosis=prescription.diagnosis,
        clinical_notes=prescription.clinical_notes,
        pdf_s3_key=prescription.pdf_s3_key,
        issued_at=prescription.issued_at,
        chemist_id=prescription.chemist_id,
        digital_signature=prescription.digital_signature,
        digital_signature_timestamp=prescription.digital_signature_timestamp,
        dispense_status=prescription.dispense_status,
        dispensed_at=prescription.dispensed_at,
        dispensed_by_chemist_id=prescription.dispensed_by_chemist_id,
        items=prescription.items,
        download_url=download_url,
        created_at=prescription.created_at,
        updated_at=prescription.updated_at,
    )


async def create_prescription(
    doctor_id: uuid.UUID | None = None,
    req: PrescriptionCreate | None = None,
    session: AsyncSession | None = None,
    chemist_id: uuid.UUID | None = None,
    *,
    doctor_user_id: uuid.UUID | None = None,
    payload: PrescriptionCreate | None = None,
) -> PrescriptionResponse:
    """Create a prescription with CMP-01 compliance gating, digital signature, and PDF generation."""
    effective_doctor_id = doctor_id if doctor_id is not None else doctor_user_id
    effective_req = req if req is not None else payload
    if effective_doctor_id is None or effective_req is None or session is None:
        raise ValueError("doctor_id, req, and session are required")

    appointment = await session.get(Appointment, effective_req.appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if appointment.doctor_id != effective_doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to prescribe for this appointment.",
        )

    if appointment.status != AppointmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prescriptions can only be issued for completed appointments.",
        )

    # CMP-01: block telemedicine-restricted drugs on video consultations.
    if appointment.mode == AppointmentMode.VIDEO:
        for item in effective_req.items:
            drug = await _find_restricted_drug(item.drug_name, session)
            if drug is not None and drug.is_telemedicine_restricted:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Medication '{item.drug_name}' is restricted for remote "
                        "teleconsultation under Indian Telemedicine Practice Guidelines."
                    ),
                )

    existing = await session.execute(
        select(Prescription).where(
            Prescription.appointment_id == effective_req.appointment_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A prescription already exists for this appointment.",
        )

    # Fetch doctor details for digital signature
    doctor = await session.get(Doctor, effective_doctor_id)
    medical_reg_number = (
        doctor.medical_reg_number
        if doctor and doctor.medical_reg_number
        else "MCI-REG-PROVISIONAL"
    )

    issued_at = datetime.now(UTC)
    effective_chemist_id = chemist_id or effective_req.chemist_id

    # Compute cryptographic HMAC-SHA256 digital signature
    signature = generate_prescription_signature(
        doctor_id=effective_doctor_id,
        medical_reg_number=medical_reg_number,
        patient_id=appointment.patient_id,
        appointment_id=appointment.id,
        items=effective_req.items,
        issued_at=issued_at,
    )

    prescription = Prescription(
        id=uuid.uuid4(),
        appointment_id=appointment.id,
        doctor_id=effective_doctor_id,
        patient_id=appointment.patient_id,
        diagnosis=effective_req.diagnosis,
        clinical_notes=effective_req.clinical_notes,
        issued_at=issued_at,
        chemist_id=effective_chemist_id,
        digital_signature=signature,
        digital_signature_timestamp=issued_at,
        dispense_status="pending",
        dispensed_at=None,
        dispensed_by_chemist_id=None,
        items=[
            PrescriptionItem(
                id=uuid.uuid4(),
                drug_name=item.drug_name,
                dosage=item.dosage,
                frequency=item.frequency,
                duration_days=item.duration_days,
                instructions=item.instructions,
            )
            for item in effective_req.items
        ],
    )
    session.add(prescription)
    await session.commit()
    await session.refresh(prescription)

    # Generate PDF (sync path for immediate download_url; Celery task also available).
    try:
        await compile_and_upload_prescription_pdf(prescription.id, session)
        await session.refresh(
            prescription, attribute_names=["items", "pdf_s3_key", "updated_at"]
        )
    except Exception as exc:
        # Prescription is persisted even if PDF upload fails; Celery can retry.
        print(f"[PRESCRIPTION] PDF compile/upload failed: {exc}")

    download_url = None
    if prescription.pdf_s3_key:
        download_url = storage_service.generate_presigned_download_url(
            bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
            s3_key=prescription.pdf_s3_key,
        )

    # Best-effort async enqueue for regeneration/retry pipelines.
    try:
        from backend.app.workers.tasks import generate_prescription_pdf_task

        generate_prescription_pdf_task.delay(str(prescription.id))
    except Exception:
        pass

    return _to_prescription_response(prescription, download_url=download_url)


async def get_prescription(
    prescription_id: uuid.UUID,
    session: AsyncSession,
    *,
    requester_id: uuid.UUID | None = None,
    require_patient: bool = False,
    require_doctor: bool = False,
) -> PrescriptionResponse:
    prescription = await session.get(
        Prescription,
        prescription_id,
        options=[selectinload(Prescription.items)],
    )
    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )

    if (
        require_patient
        and requester_id is not None
        and prescription.patient_id != requester_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this prescription.",
        )
    if (
        require_doctor
        and requester_id is not None
        and prescription.doctor_id != requester_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this prescription.",
        )

    download_url = None
    if prescription.pdf_s3_key:
        download_url = storage_service.generate_presigned_download_url(
            bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
            s3_key=prescription.pdf_s3_key,
        )
    return _to_prescription_response(prescription, download_url=download_url)


async def search_drugs(
    query: str,
    session: AsyncSession,
    *,
    limit: int = 20,
) -> list[DrugMasterResponse]:
    await seed_default_drugs(session)
    await session.commit()

    pattern = f"%{query.strip()}%"
    stmt = (
        select(DrugMaster)
        .where(
            or_(
                DrugMaster.brand_name.ilike(pattern),
                DrugMaster.generic_name.ilike(pattern),
            )
        )
        .order_by(DrugMaster.brand_name.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [DrugMasterResponse.model_validate(d) for d in result.scalars().all()]


async def list_patient_prescriptions(
    patient_id: uuid.UUID,
    session: AsyncSession,
) -> list[PrescriptionResponse]:
    stmt = (
        select(Prescription)
        .where(Prescription.patient_id == patient_id)
        .options(selectinload(Prescription.items))
        .order_by(Prescription.issued_at.desc())
    )
    result = await session.execute(stmt)
    prescriptions = result.scalars().all()

    responses: list[PrescriptionResponse] = []
    for rx in prescriptions:
        download_url = None
        if rx.pdf_s3_key:
            download_url = storage_service.generate_presigned_download_url(
                bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
                s3_key=rx.pdf_s3_key,
            )
        responses.append(_to_prescription_response(rx, download_url=download_url))
    return responses


async def get_patient_prescription_download_url(
    prescription_id: uuid.UUID,
    patient_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, str]:
    prescription = await session.get(Prescription, prescription_id)
    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )
    if prescription.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to download this prescription.",
        )
    if not prescription.pdf_s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription PDF is not available yet.",
        )
    url = storage_service.generate_presigned_download_url(
        bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
        s3_key=prescription.pdf_s3_key,
    )
    return {"prescription_id": str(prescription.id), "download_url": url}
