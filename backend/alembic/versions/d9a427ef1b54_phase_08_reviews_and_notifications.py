"""phase_08_reviews_and_notifications"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d9a427ef1b54"
down_revision = "175cde4afc03"
branch_labels = None
depends_on = None

def upgrade() -> None:
    review_status = postgresql.ENUM("published", "flagged", "hidden", "removed", name="review_status")
    notification_type = postgresql.ENUM("appointment_reminder", "status_update", "general", name="notification_type")
    notification_channel = postgresql.ENUM("sms", "email", "push", "in_app", name="notification_channel")
    notification_status = postgresql.ENUM("pending", "sent", "failed", name="notification_status")
    for enum in (review_status, notification_type, notification_channel, notification_status): enum.create(op.get_bind(), checkfirst=True)
    op.add_column("doctors", sa.Column("average_rating", sa.Numeric(3, 2), server_default="0.00", nullable=False))
    op.add_column("doctors", sa.Column("review_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("appointments", sa.Column("reminder_sent", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_index(op.f("ix_appointments_reminder_sent"), "appointments", ["reminder_sent"])
    op.create_table("reviews", sa.Column("id", sa.UUID(), nullable=False), sa.Column("appointment_id", sa.UUID(), nullable=False), sa.Column("doctor_id", sa.UUID(), nullable=False), sa.Column("patient_id", sa.UUID(), nullable=False), sa.Column("rating", sa.Integer(), nullable=False), sa.Column("review_text", sa.Text(), nullable=True), sa.Column("status", postgresql.ENUM(name="review_status", create_type=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["doctor_id"], ["doctors.user_id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("appointment_id"))
    op.create_index(op.f("ix_reviews_appointment_id"), "reviews", ["appointment_id"], unique=True); op.create_index(op.f("ix_reviews_doctor_id"), "reviews", ["doctor_id"]); op.create_index(op.f("ix_reviews_patient_id"), "reviews", ["patient_id"]); op.create_index(op.f("ix_reviews_status"), "reviews", ["status"])
    op.create_table("notifications", sa.Column("id", sa.UUID(), nullable=False), sa.Column("user_id", sa.UUID(), nullable=False), sa.Column("appointment_id", sa.UUID(), nullable=True), sa.Column("type", postgresql.ENUM(name="notification_type", create_type=False), nullable=False), sa.Column("channel", postgresql.ENUM(name="notification_channel", create_type=False), nullable=False), sa.Column("status", postgresql.ENUM(name="notification_status", create_type=False), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"]); op.create_index(op.f("ix_notifications_appointment_id"), "notifications", ["appointment_id"])

def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_appointment_id"), table_name="notifications"); op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications"); op.drop_table("notifications")
    for name in ("ix_reviews_status", "ix_reviews_patient_id", "ix_reviews_doctor_id", "ix_reviews_appointment_id"): op.drop_index(op.f(name), table_name="reviews")
    op.drop_table("reviews"); op.drop_index(op.f("ix_appointments_reminder_sent"), table_name="appointments"); op.drop_column("appointments", "reminder_sent"); op.drop_column("doctors", "review_count"); op.drop_column("doctors", "average_rating")
    for name in ("notification_status", "notification_channel", "notification_type", "review_status"): sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
