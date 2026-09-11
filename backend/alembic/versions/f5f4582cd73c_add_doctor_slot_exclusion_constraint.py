"""add_doctor_slot_exclusion_constraint

Revision ID: f5f4582cd73c
Revises: 6416f7d5a8d6
Create Date: 2026-09-11 16:37:38.985562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5f4582cd73c'
down_revision: Union[str, Sequence[str], None] = '6416f7d5a8d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    ALTER TABLE appointments
    ADD CONSTRAINT no_overlapping_doctor_appointments
    EXCLUDE USING gist (
        doctor_id WITH =,
        tstzrange(slot_start, slot_end) WITH &&
    )
    WHERE (status NOT IN ('CANCELLED', 'NO_SHOW'));
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    ALTER TABLE appointments
    DROP CONSTRAINT IF EXISTS no_overlapping_doctor_appointments;
    """)
