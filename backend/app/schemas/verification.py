import uuid
from datetime import datetime

from backend.app.models.doctor import VerificationStatus
from backend.app.models.verification import DocumentType
from backend.app.schemas.doctor import DoctorRead
from pydantic import BaseModel, ConfigDict, Field


class DocumentPresignRequest(BaseModel):
    doc_type: DocumentType
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(default="application/pdf")

class DocumentPresignResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int = 3600

class DocumentConfirmRequest(BaseModel):
    doc_type: DocumentType
    file_name: str
    s3_key: str

class DoctorDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_id: uuid.UUID
    doc_type: DocumentType
    file_name: str
    s3_key: str
    uploaded_at: datetime

class VerificationTransitionRequest(BaseModel):
    new_status: VerificationStatus
    reason_text: str | None = Field(None, description="Mandatory when status is rejected or suspended")
    review_notes: str | None = None

class VerificationQueueItemRead(BaseModel):
    doctor: DoctorRead
    documents: list[DoctorDocumentRead] = []
