import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis import publish_event
from backend.app.models.chat import ChatMessage


async def save_chat_message(
    session: AsyncSession, appointment_id: uuid.UUID, sender_id: uuid.UUID, sender_role: str,
    message_text: str, file_s3_key: Optional[str] = None,
) -> ChatMessage:
    message = ChatMessage(
        appointment_id=appointment_id, sender_id=sender_id, sender_role=sender_role,
        message_text=message_text, file_s3_key=file_s3_key,
    )
    session.add(message)
    await session.flush()
    try:
        await publish_event("appointment:events", "chat_message_persisted", {
            "appointment_id": str(appointment_id), "message_id": str(message.id),
            "sender_id": str(sender_id), "sender_role": sender_role,
        })
    except Exception:
        pass
    await session.commit()
    await session.refresh(message)
    return message


async def get_chat_history(session: AsyncSession, appointment_id: uuid.UUID, limit: int = 100) -> List[ChatMessage]:
    result = await session.execute(select(ChatMessage).where(
        ChatMessage.appointment_id == appointment_id
    ).order_by(ChatMessage.created_at.asc()).limit(min(max(limit, 1), 100)))
    return list(result.scalars().all())
