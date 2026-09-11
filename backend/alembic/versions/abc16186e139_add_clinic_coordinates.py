"""add_clinic_coordinates

Revision ID: abc16186e139
Revises: d9a427ef1b54
Create Date: 2026-09-11 18:54:34.752334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc16186e139'
down_revision: Union[str, Sequence[str], None] = 'd9a427ef1b54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clinics', sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column('clinics', sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clinics', 'longitude')
    op.drop_column('clinics', 'latitude')
