import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CancellationRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class CancellationResponse(BaseModel):
    appointment_id: uuid.UUID
    status: str
    is_refunded: bool
    refund_amount: Decimal
    refund_id: Optional[str] = None
    message: str
