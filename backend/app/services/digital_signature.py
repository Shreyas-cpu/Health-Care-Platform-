"""Cryptographic Digital Signature Engine for Medical Prescriptions.

Signs doctor credentials, patient identity, appointment details, and medication items
using HMAC-SHA256 to ensure non-repudiation and tamper-evident prescription integrity
as required under Indian Telemedicine Practice Guidelines and IT Act 2000.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.core.config import settings


def canonicalize_items(items: list[Any]) -> list[dict[str, Any]]:
    """Normalize medication items into a deterministic, sorted representation."""
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            drug_name = item.get("drug_name", "")
            dosage = item.get("dosage", "")
            frequency = item.get("frequency", "")
            duration_days = item.get("duration_days", 0)
            instructions = item.get("instructions")
        else:
            drug_name = getattr(item, "drug_name", "")
            dosage = getattr(item, "dosage", "")
            frequency = getattr(item, "frequency", "")
            duration_days = getattr(item, "duration_days", 0)
            instructions = getattr(item, "instructions", None)

        normalized.append(
            {
                "dosage": str(dosage).strip(),
                "drug_name": str(drug_name).strip().upper(),
                "duration_days": int(duration_days),
                "frequency": str(frequency).strip(),
                "instructions": str(instructions).strip() if instructions else "",
            }
        )

    normalized.sort(key=lambda x: (x["drug_name"], x["dosage"], x["frequency"]))
    return normalized


def build_signature_payload(
    doctor_id: uuid.UUID | str,
    medical_reg_number: str,
    patient_id: uuid.UUID | str,
    appointment_id: uuid.UUID | str,
    items: list[Any],
    issued_at: datetime,
) -> str:
    """Construct deterministic canonical JSON string for HMAC computation."""
    if issued_at.tzinfo is None:
        issued_at_utc = issued_at.replace(tzinfo=UTC)
    else:
        issued_at_utc = issued_at.astimezone(UTC)
    issued_at_str = issued_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    payload_dict = {
        "appointment_id": str(appointment_id),
        "doctor_id": str(doctor_id),
        "issued_at": issued_at_str,
        "items": canonicalize_items(items),
        "medical_reg_number": str(medical_reg_number).strip().upper(),
        "patient_id": str(patient_id),
    }
    return json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))


def generate_prescription_signature(
    doctor_id: uuid.UUID | str,
    medical_reg_number: str,
    patient_id: uuid.UUID | str,
    appointment_id: uuid.UUID | str,
    items: list[Any],
    issued_at: datetime,
    secret_key: str | None = None,
) -> str:
    """Generate SHA-256 HMAC cryptographic digital signature digest."""
    key = (secret_key or settings.JWT_SECRET_KEY).encode("utf-8")
    payload = build_signature_payload(
        doctor_id=doctor_id,
        medical_reg_number=medical_reg_number,
        patient_id=patient_id,
        appointment_id=appointment_id,
        items=items,
        issued_at=issued_at,
    ).encode("utf-8")

    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_prescription_signature(
    prescription: Any,
    secret_key: str | None = None,
    medical_reg_number: str | None = None,
) -> bool:
    """Validate signature integrity of a prescription.

    Returns True if valid and untampered, False otherwise.
    """
    if (
        not hasattr(prescription, "digital_signature")
        or not prescription.digital_signature
    ):
        return False

    reg_num = medical_reg_number
    if not reg_num and hasattr(prescription, "doctor") and prescription.doctor:
        reg_num = getattr(prescription.doctor, "medical_reg_number", None)
    if not reg_num:
        reg_num = "UNKNOWN-REG"

    timestamp = getattr(
        prescription,
        "digital_signature_timestamp",
        getattr(prescription, "issued_at", None),
    )
    if not timestamp:
        return False

    expected_signature = generate_prescription_signature(
        doctor_id=prescription.doctor_id,
        medical_reg_number=reg_num,
        patient_id=prescription.patient_id,
        appointment_id=prescription.appointment_id,
        items=prescription.items,
        issued_at=timestamp,
        secret_key=secret_key,
    )
    return hmac.compare_digest(prescription.digital_signature, expected_signature)
