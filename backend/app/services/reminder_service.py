from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.appointment import Appointment, AppointmentStatus
from backend.app.models.notification import Notification, NotificationChannel, NotificationStatus, NotificationType

async def dispatch_upcoming_reminders(session: AsyncSession) -> list[Notification]:
    now = datetime.now(timezone.utc)
    appointments = (
        await session.execute(
            select(Appointment).where(
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.REQUESTED]),
                Appointment.reminder_sent.is_(False),
                Appointment.slot_start.between(now - timedelta(minutes=5), now + timedelta(hours=2)),
            )
        )
    ).scalars().all()
    notifications = []
    for appt in appointments:
        notification = Notification(
            user_id=appt.patient_id,
            appointment_id=appt.id,
            type=NotificationType.APPOINTMENT_REMINDER,
            channel=NotificationChannel.SMS,
            status=NotificationStatus.SENT,
            message=f"Reminder: Your appointment is scheduled at {appt.slot_start.isoformat()}",
            sent_at=now,
        )
        session.add(notification)
        appt.reminder_sent = True
        notifications.append(notification)
    await session.flush()
    await session.commit()
    for notification in notifications:
        await session.refresh(notification)
    return notifications

