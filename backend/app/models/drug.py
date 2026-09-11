import uuid

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, String, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column


class DrugMaster(Base, TimestampMixin):
    """Static medication catalogue with telemedicine restriction flags (CMP-01)."""

    __tablename__ = "drug_master"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    generic_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dosage_form: Mapped[str] = mapped_column(String(100), nullable=False)
    is_telemedicine_restricted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<DrugMaster {self.brand_name} ({self.generic_name}) "
            f"restricted={self.is_telemedicine_restricted}>"
        )


DEFAULT_DRUGS: list[dict] = [
    {
        "brand_name": "Crocin",
        "generic_name": "Paracetamol",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": False,
    },
    {
        "brand_name": "Mox 500",
        "generic_name": "Amoxicillin",
        "dosage_form": "capsule",
        "is_telemedicine_restricted": False,
    },
    {
        "brand_name": "Pan 40",
        "generic_name": "Pantoprazole",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": False,
    },
    {
        # Habit-forming Schedule X
        "brand_name": "Alprax",
        "generic_name": "Alprazolam",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": True,
    },
    {
        # Narcotic Schedule X
        "brand_name": "Corex",
        "generic_name": "Codeine Phosphate",
        "dosage_form": "syrup",
        "is_telemedicine_restricted": True,
    },
    {
        "brand_name": "Azithral 500",
        "generic_name": "Azithromycin",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": False,
    },
    {
        "brand_name": "Glycomet 500",
        "generic_name": "Metformin",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": False,
    },
    {
        "brand_name": "Cetzine",
        "generic_name": "Cetirizine",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": False,
    },
    {
        # Restricted
        "brand_name": "Lonazep",
        "generic_name": "Clonazepam",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": True,
    },
    {
        # Restricted
        "brand_name": "Ultram",
        "generic_name": "Tramadol",
        "dosage_form": "tablet",
        "is_telemedicine_restricted": True,
    },
]


async def seed_default_drugs(session: AsyncSession) -> int:
    """Seed common Indian medicines if the drug_master table is empty."""
    result = await session.execute(select(DrugMaster.id).limit(1))
    if result.scalar_one_or_none() is not None:
        return 0

    drugs = [DrugMaster(**payload) for payload in DEFAULT_DRUGS]
    session.add_all(drugs)
    await session.flush()
    return len(drugs)
