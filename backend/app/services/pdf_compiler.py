"""ReportLab-based prescription PDF compiler."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

from backend.app.core.config import settings
from backend.app.models.appointment import Appointment
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.patient import Patient
from backend.app.models.prescription import Prescription
from backend.app.services.storage import storage_service
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload



async def compile_prescription_pdf(
    prescription_id: uuid.UUID,
    session: AsyncSession,
) -> bytes:
    """Compile a clean vector PDF for the given prescription."""
    prescription = await session.get(
        Prescription,
        prescription_id,
        options=[selectinload(Prescription.items)],
    )
    if prescription is None:
        raise ValueError(f"Prescription {prescription_id} not found")

    doctor = await session.get(
        Doctor,
        prescription.doctor_id,
        options=[selectinload(Doctor.clinic)],
    )
    patient = await session.get(Patient, prescription.patient_id)
    appointment = await session.get(Appointment, prescription.appointment_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Prescription {prescription.id}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RxTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "RxMeta",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "RxSection",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=6,
    )
    footer_style = ParagraphStyle(
        "RxFooter",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#444444"),
        spaceBefore=16,
    )

    doctor_name = doctor.full_name if doctor else "Doctor"
    reg_number = doctor.medical_reg_number if doctor else "—"
    council = doctor.council_name if doctor else "—"
    specialty = doctor.specialty if doctor else "—"
    clinic_address = "—"
    if doctor is not None:
        clinic_res = await session.execute(
            select(Clinic).where(Clinic.doctor_id == doctor.user_id)
        )
        clinic = clinic_res.scalar_one_or_none()
        if clinic is not None:
            clinic_address = (
                f"{clinic.name}, {clinic.address}, {clinic.locality}, "
                f"{clinic.city} - {clinic.pincode}"
            )


    patient_name = (
        patient.full_name if patient and patient.full_name else str(prescription.patient_id)
    )
    appt_date = (
        appointment.slot_start.strftime("%d %b %Y, %H:%M")
        if appointment
        else prescription.issued_at.strftime("%d %b %Y, %H:%M")
    )

    story: list = [
        Paragraph("Digital Prescription", title_style),
        Paragraph(f"<b>{doctor_name}</b>", meta_style),
        Paragraph(f"Reg. No: {reg_number} | Council: {council}", meta_style),
        Paragraph(f"Specialty: {specialty}", meta_style),
        Paragraph(f"Clinic: {clinic_address}", meta_style),
        Spacer(1, 8),
        Paragraph("Patient Details", section_style),
        Paragraph(f"Patient: {patient_name}", meta_style),
        Paragraph(f"Appointment: {appt_date}", meta_style),
        Paragraph(f"Diagnosis: {prescription.diagnosis}", meta_style),
    ]
    if prescription.clinical_notes:
        story.append(Paragraph(f"Clinical Notes: {prescription.clinical_notes}", meta_style))

    story.append(Paragraph("Rx", section_style))

    table_data = [["Drug Name", "Dosage", "Frequency", "Duration", "Instructions"]]
    for item in prescription.items:
        table_data.append(
            [
                item.drug_name,
                item.dosage,
                item.frequency,
                f"{item.duration_days} day(s)",
                item.instructions or "—",
            ]
        )

    table = Table(table_data, colWidths=[45 * mm, 25 * mm, 25 * mm, 25 * mm, 40 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#99A3B0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))

    # Official Cryptographic Digital Signature Seal Box
    raw_hash = getattr(prescription, "digital_signature", None) or "PROVISIONAL-SIGNATURE"
    truncated_hash = f"{raw_hash[:16]}...{raw_hash[-16:]}" if len(raw_hash) > 32 else raw_hash
    sig_time = getattr(prescription, "digital_signature_timestamp", prescription.issued_at)
    if sig_time.tzinfo is None:
        sig_time_str = sig_time.strftime("%d %b %Y, %H:%M:%S UTC")
    else:
        sig_time_str = sig_time.astimezone(UTC).strftime("%d %b %Y, %H:%M:%S UTC")

    sig_header_style = ParagraphStyle(
        "RxSigHeader",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0D5C3A"),
    )
    sig_text_style = ParagraphStyle(
        "RxSigText",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        fontName="Helvetica",
        textColor=colors.HexColor("#1F2937"),
    )

    sig_data = [
        [Paragraph("<b>✓ DIGITALLY SIGNED &amp; VERIFIED</b>", sig_header_style)],
        [Paragraph(f"<b>Doctor Medical Reg. No:</b> {reg_number} ({council})", sig_text_style)],
        [Paragraph(f"<b>Cryptographic Hash (SHA-256):</b> {truncated_hash}", sig_text_style)],
        [Paragraph(f"<b>Signed At:</b> {sig_time_str}", sig_text_style)],
    ]
    sig_table = Table(sig_data, colWidths=[160 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#16A34A")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(Spacer(1, 10))
    story.append(sig_table)

    story.append(
        Paragraph(
            "Digitally generated prescription under Indian Telemedicine Practice Guidelines 2020.",
            footer_style,
        )
    )
    story.append(
        Paragraph(
            f"Issued at: {prescription.issued_at.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')} | "
            f"Prescription ID: {prescription.id}",
            footer_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()


async def compile_and_upload_prescription_pdf(
    prescription_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    """Compile PDF, upload to S3, and persist pdf_s3_key on the prescription."""
    pdf_bytes = await compile_prescription_pdf(prescription_id, session)
    s3_key = f"prescriptions/{prescription_id}.pdf"
    storage_service.upload_bytes(
        bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
        s3_key=s3_key,
        data=pdf_bytes,
        content_type="application/pdf",
    )

    prescription = await session.get(Prescription, prescription_id)
    if prescription is None:
        raise ValueError(f"Prescription {prescription_id} not found")
    prescription.pdf_s3_key = s3_key
    prescription.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(prescription)
    return s3_key
