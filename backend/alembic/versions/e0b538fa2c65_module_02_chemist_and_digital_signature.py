"""module_02_chemist_and_digital_signature

Revision ID: e0b538fa2c65
Revises: d9a427ef1b54
Create Date: 2026-09-11 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e0b538fa2c65'
down_revision: Union[str, Sequence[str], None] = 'abc16186e139'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'chemist' and 'CHEMIST' values to user_role enum
    op.execute(sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'chemist'"))
    op.execute(sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'CHEMIST'"))


    # Create chemists table
    op.create_table(
        'chemists',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('pharmacy_name', sa.String(length=255), nullable=False),
        sa.Column('license_number', sa.String(length=100), nullable=False),
        sa.Column('clinic_id', sa.UUID(), nullable=True),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('locality', sa.String(length=100), nullable=False),
        sa.Column('pincode', sa.String(length=10), nullable=False),
        sa.Column('contact_number', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(op.f('ix_chemists_user_id'), 'chemists', ['user_id'], unique=True)
    op.create_index(op.f('ix_chemists_license_number'), 'chemists', ['license_number'], unique=True)
    op.create_index(op.f('ix_chemists_clinic_id'), 'chemists', ['clinic_id'], unique=False)
    op.create_index(op.f('ix_chemists_city'), 'chemists', ['city'], unique=False)
    op.create_index(op.f('ix_chemists_locality'), 'chemists', ['locality'], unique=False)

    # Add columns to prescriptions table
    op.add_column('prescriptions', sa.Column('chemist_id', sa.UUID(), nullable=True))
    op.add_column('prescriptions', sa.Column('digital_signature', sa.String(length=255), server_default='', nullable=False))
    op.add_column('prescriptions', sa.Column('digital_signature_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('prescriptions', sa.Column('dispense_status', sa.String(length=50), server_default='pending', nullable=False))
    op.add_column('prescriptions', sa.Column('dispensed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('prescriptions', sa.Column('dispensed_by_chemist_id', sa.UUID(), nullable=True))

    op.create_index(op.f('ix_prescriptions_chemist_id'), 'prescriptions', ['chemist_id'], unique=False)
    op.create_foreign_key('fk_prescriptions_chemist_id', 'prescriptions', 'chemists', ['chemist_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_prescriptions_dispensed_by_chemist_id', 'prescriptions', 'chemists', ['dispensed_by_chemist_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_prescriptions_dispensed_by_chemist_id', 'prescriptions', type_='foreignkey')
    op.drop_constraint('fk_prescriptions_chemist_id', 'prescriptions', type_='foreignkey')
    op.drop_index(op.f('ix_prescriptions_chemist_id'), table_name='prescriptions')

    op.drop_column('prescriptions', 'dispensed_by_chemist_id')
    op.drop_column('prescriptions', 'dispensed_at')
    op.drop_column('prescriptions', 'dispense_status')
    op.drop_column('prescriptions', 'digital_signature_timestamp')
    op.drop_column('prescriptions', 'digital_signature')
    op.drop_column('prescriptions', 'chemist_id')

    op.drop_index(op.f('ix_chemists_locality'), table_name='chemists')
    op.drop_index(op.f('ix_chemists_city'), table_name='chemists')
    op.drop_index(op.f('ix_chemists_clinic_id'), table_name='chemists')
    op.drop_index(op.f('ix_chemists_license_number'), table_name='chemists')
    op.drop_index(op.f('ix_chemists_user_id'), table_name='chemists')
    op.drop_table('chemists')
