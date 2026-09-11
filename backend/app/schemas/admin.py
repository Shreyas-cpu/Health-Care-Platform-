from decimal import Decimal
from pydantic import BaseModel, Field

class PlatformTelemetryResponse(BaseModel):
    total_verified_doctors: int
    total_confirmed_bookings: int
    total_completed_consultations: int
    gross_transaction_value: Decimal
    total_registered_chemists: int = 0
    total_patient_documents: int = 0


class ReminderDispatchResponse(BaseModel):
    dispatched_count: int
    timestamp: str


class ChemistStatusUpdateAction(BaseModel):
    action: str = Field(..., description="Action to perform: activate, suspend, or deactivate")
    reason_text: str = Field(..., min_length=1, description="Mandatory reason for chemist status update")
