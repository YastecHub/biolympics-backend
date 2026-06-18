"""Append-only audit logging for sensitive administrative actions."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.auth import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    reason: str | None = None,
    changes: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        actor_id=actor_id,
        actor_email=actor_email,
        reason=reason,
        changes=changes or {},
        request_id=request_id,
        created_at=utcnow(),
    )
    db.add(entry)
    await db.flush()
    return entry
