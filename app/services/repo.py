"""Small shared query helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Department, Sport, Tournament


async def current_tournament(db: AsyncSession) -> Tournament | None:
    return (
        await db.execute(select(Tournament).where(Tournament.is_current.is_(True)).limit(1))
    ).scalar_one_or_none()


async def current_tournament_id(db: AsyncSession) -> uuid.UUID | None:
    t = await current_tournament(db)
    return t.id if t else None


async def sport_by_slug(db: AsyncSession, slug: str) -> Sport | None:
    return (await db.execute(select(Sport).where(Sport.slug == slug))).scalar_one_or_none()


async def department_by_slug(db: AsyncSession, slug: str) -> Department | None:
    return (
        await db.execute(select(Department).where(Department.slug == slug))
    ).scalar_one_or_none()
