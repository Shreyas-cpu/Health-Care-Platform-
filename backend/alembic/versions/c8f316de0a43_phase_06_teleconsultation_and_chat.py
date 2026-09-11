"""phase_06_teleconsultation_and_chat

Revision ID: c8f316de0a43
Revises: b7e205dc0e32
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c8f316de0a43"
down_revision: Union[str, Sequence[str], None] = "b7e205dc0e32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session_status = postgresql.ENUM(
        "SCHEDULED", "WAITING_ROOM", "LIVE", "COMPLETED", "FOLLOW_UP_SCHEDULED",
        name="session_status",
    )
    session_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "teleconsultation_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("appointment_id", sa.UUID(), nullable=False),
        sa.Column("room_name", sa.String(length=100), nullable=False),
        sa.Column("status", postgresql.ENUM(name="session_status", create_type=False), nullable=False),
        sa.Column("patient_joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("doctor_joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recording_enabled", sa.Boolean(), nullable=False),
        sa.Column("doctor_recording_consent", sa.Boolean(), nullable=False),
        sa.Column("patient_recording_consent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("appointment_id"),
    )
    op.create_index(op.f("ix_teleconsultation_sessions_appointment_id"), "teleconsultation_sessions", ["appointment_id"], unique=True)
    op.create_index(op.f("ix_teleconsultation_sessions_status"), "teleconsultation_sessions", ["status"], unique=False)
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("appointment_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("sender_role", sa.String(length=20), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("file_s3_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_appointment_id"), "chat_messages", ["appointment_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_sender_id"), "chat_messages", ["sender_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_sender_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_appointment_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_teleconsultation_sessions_status"), table_name="teleconsultation_sessions")
    op.drop_index(op.f("ix_teleconsultation_sessions_appointment_id"), table_name="teleconsultation_sessions")
    op.drop_table("teleconsultation_sessions")
    sa.Enum(name="session_status").drop(op.get_bind(), checkfirst=True)
