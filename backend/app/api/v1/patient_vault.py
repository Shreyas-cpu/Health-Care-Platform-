import uuid

from backend.app.api.deps import get_current_user, require_roles
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.appointment import Appointment
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.patient_document import PatientDocument
from backend.app.models.prescription import Prescription
from backend.app.models.user import User, UserRole
from backend.app.schemas.patient_document import (
    AppointmentHistoryItem,
    PatientDocumentResponse,
    PatientVaultResponse,
)
from backend.app.schemas.prescription import PrescriptionResponse
from backend.app.services.prescription_service import _to_prescription_response
from backend.app.services.storage import storage_service
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/patients/me", tags=["Patient Health Vault & History"])


@router.post(
    "/documents",
    response_model=PatientDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_patient_document(
    file: UploadFile = File(...),
    doc_type: str = Form("medical_history"),
    notes: str | None = Form(None),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Upload health records, past prescriptions, scans, or lab reports to patient vault."""
    contents = await file.read()
    file_size = len(contents)
    if file_size > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum permitted limit of 25MB.",
        )

    file_ext = file.filename.split(".")[-1] if "." in file.filename else "pdf"
    doc_id = uuid.uuid4()
    s3_key = f"patient-vault/{current_user.id}/{doc_id}.{file_ext}"

    content_type = file.content_type or "application/octet-stream"
    storage_service.upload_bytes(
        bucket_name=settings.S3_BUCKET_PATIENT_DOCUMENTS,
        s3_key=s3_key,
        data=contents,
        content_type=content_type,
    )

    doc = PatientDocument(
        id=doc_id,
        patient_id=current_user.id,
        doc_type=doc_type.strip(),
        file_name=file.filename,
        s3_key=s3_key,
        file_size_bytes=file_size,
        notes=notes.strip() if notes else None,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    download_url = storage_service.generate_presigned_download_url(
        bucket_name=settings.S3_BUCKET_PATIENT_DOCUMENTS,
        s3_key=s3_key,
    )

    return PatientDocumentResponse(
        id=doc.id,
        patient_id=doc.patient_id,
        doc_type=doc.doc_type,
        file_name=doc.file_name,
        file_size_bytes=doc.file_size_bytes,
        notes=doc.notes,
        created_at=doc.created_at,
        download_url=download_url,
    )


@router.get("/documents", response_model=PatientVaultResponse)
async def get_patient_vault(
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve all uploaded medical documents alongside system-generated consultation prescriptions."""
    # 1. Fetch uploaded documents
    docs_stmt = (
        select(PatientDocument)
        .where(PatientDocument.patient_id == current_user.id)
        .order_by(PatientDocument.created_at.desc())
    )
    docs_result = await session.execute(docs_stmt)
    documents = docs_result.scalars().all()

    uploaded_docs: list[PatientDocumentResponse] = []
    for doc in documents:
        dl_url = storage_service.generate_presigned_download_url(
            bucket_name=settings.S3_BUCKET_PATIENT_DOCUMENTS,
            s3_key=doc.s3_key,
        )
        uploaded_docs.append(
            PatientDocumentResponse(
                id=doc.id,
                patient_id=doc.patient_id,
                doc_type=doc.doc_type,
                file_name=doc.file_name,
                file_size_bytes=doc.file_size_bytes,
                notes=doc.notes,
                created_at=doc.created_at,
                download_url=dl_url,
            )
        )

    # 2. Fetch system-generated prescriptions
    rx_stmt = (
        select(Prescription)
        .where(Prescription.patient_id == current_user.id)
        .options(selectinload(Prescription.items))
        .order_by(Prescription.issued_at.desc())
    )
    rx_result = await session.execute(rx_stmt)
    prescriptions = rx_result.scalars().all()

    rx_responses: list[PrescriptionResponse] = []
    for rx in prescriptions:
        rx_url = None
        if rx.pdf_s3_key:
            rx_url = storage_service.generate_presigned_download_url(
                bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
                s3_key=rx.pdf_s3_key,
            )
        rx_responses.append(_to_prescription_response(rx, download_url=rx_url))

    return PatientVaultResponse(
        uploaded_documents=uploaded_docs,
        prescriptions=rx_responses,
    )


@router.get("/documents/{document_id}/download")
async def download_patient_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get presigned download URL for a specific uploaded document."""
    doc = await session.get(PatientDocument, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Security check: must be owner or super admin/reviewer
    is_owner = doc.patient_id == current_user.id
    is_privileged = current_user.role in {
        UserRole.SUPER_ADMIN,
        UserRole.VERIFICATION_REVIEWER,
        UserRole.DOCTOR,
    }
    if not is_owner and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this document.",
        )

    url = storage_service.generate_presigned_download_url(
        bucket_name=settings.S3_BUCKET_PATIENT_DOCUMENTS,
        s3_key=doc.s3_key,
    )
    return {"download_url": url, "file_name": doc.file_name}


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """Delete an uploaded health document from patient vault."""
    doc = await session.get(PatientDocument, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    if doc.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete documents belonging to another user.",
        )

    await session.delete(doc)
    await session.commit()


@router.get("/appointments/history", response_model=list[AppointmentHistoryItem])
async def get_appointment_history(
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    """
    Complete appointment history for the patient with doctor details,
    clinic geolocation & Google Maps redirection link, and attached prescriptions.
    """
    stmt = (
        select(Appointment)
        .where(Appointment.patient_id == current_user.id)
        .order_by(Appointment.slot_start.desc())
    )
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    history: list[AppointmentHistoryItem] = []
    for appt in appointments:
        # Load doctor
        doctor = (
            await session.execute(
                select(Doctor).where(Doctor.user_id == appt.doctor_id)
            )
        ).scalar_one_or_none()
        doctor_name = doctor.full_name if doctor else "Doctor"
        specialty = doctor.specialty if doctor else "General Physician"

        # Load clinic
        clinic = None
        if appt.clinic_id:
            clinic = await session.get(Clinic, appt.clinic_id)
        elif doctor and doctor.clinic:
            clinic = doctor.clinic

        google_maps_url = clinic.google_maps_url if clinic else None
        clinic_name = clinic.name if clinic else None
        clinic_address = clinic.address if clinic else None
        clinic_city = clinic.city if clinic else None

        # Load prescription if completed
        rx_stmt = select(Prescription).where(Prescription.appointment_id == appt.id)
        rx = (await session.execute(rx_stmt)).scalar_one_or_none()

        prescription_id = rx.id if rx else None
        prescription_dl_url = None
        if rx and rx.pdf_s3_key:
            prescription_dl_url = storage_service.generate_presigned_download_url(
                bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
                s3_key=rx.pdf_s3_key,
            )

        history.append(
            AppointmentHistoryItem(
                id=appt.id,
                appointment_id=appt.id,
                doctor_id=appt.doctor_id,
                doctor_name=doctor_name,
                specialty=specialty,
                clinic_id=appt.clinic_id,
                clinic_name=clinic_name,
                clinic_address=clinic_address,
                clinic_city=clinic_city,
                google_maps_url=google_maps_url,
                mode=appt.mode.value if hasattr(appt.mode, "value") else str(appt.mode),
                status=appt.status.value
                if hasattr(appt.status, "value")
                else str(appt.status),
                slot_start=appt.slot_start,
                slot_end=appt.slot_end,
                fee_amount=appt.fee_amount,
                payment_status=appt.payment_status.value
                if hasattr(appt.payment_status, "value")
                else str(appt.payment_status),
                prescription_id=prescription_id,
                prescription_download_url=prescription_dl_url,
            )
        )

    return history
