import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.audit import AuditLog

async def record_audit_log(
    admin_user_id: uuid.UUID,
    target_entity_type: str,
    target_entity_id: uuid.UUID,
    action: str,
    reason: str,
    session: AsyncSession,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """
    RUL-04: Immutable audit logging.
    Every administrative action that changes doctor status, payments, or published content
    must write an immutable audit log record within the same database transaction.
    """
    if not reason or not reason.strip():
        raise ValueError("Audit log requires a non-empty, descriptive reason.")

    audit_entry = AuditLog(
        id=uuid.uuid4(),
        admin_user_id=admin_user_id,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        action=action,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason.strip(),
        ip_address=ip_address
    )
    session.add(audit_entry)
    await session.flush()
    return audit_entry
