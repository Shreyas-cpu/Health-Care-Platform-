from decimal import Decimal
from pydantic import BaseModel

class PlatformTelemetryResponse(BaseModel):
    total_verified_doctors: int
    total_confirmed_bookings: int
    total_completed_consultations: int
    gross_transaction_value: Decimal
