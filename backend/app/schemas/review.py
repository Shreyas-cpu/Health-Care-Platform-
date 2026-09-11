import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from backend.app.models.review import ReviewStatus

class ReviewCreate(BaseModel):
    appointment_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    review_text: str | None = Field(None, max_length=1000)

class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; appointment_id: uuid.UUID; doctor_id: uuid.UUID; patient_id: uuid.UUID
    rating: int; review_text: str | None; status: ReviewStatus; created_at: datetime; updated_at: datetime

class ReviewModerationAction(BaseModel):
    action: str = Field(..., pattern="^(hide|remove|approve)$")
    reason_text: str = Field(..., min_length=3)
