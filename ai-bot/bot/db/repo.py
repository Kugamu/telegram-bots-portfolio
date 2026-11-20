"""Шар доступу до даних."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ChatMessage, Lead, LeadStatus, User


async def upsert_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(id=tg_id, username=username, full_name=full_name)
        session.add(user)
    else:
        user.username, user.full_name, user.is_blocked = username, full_name, False
    await session.commit()
    return user


# ---------- історія діалогу ----------
async def add_message(session: AsyncSession, user_id: int, role: str, content: str,
                      input_tokens: int = 0, output_tokens: int = 0) -> None:
    session.add(ChatMessage(user_id=user_id, role=role, content=content,
                            input_tokens=input_tokens, output_tokens=output_tokens))
    await session.commit()


async def get_history(session: AsyncSession, user_id: int, limit: int) -> list[dict]:
    """Останні `limit` повідомлень у форматі Messages API (хронологічно, першим — user)."""
    rows = list(await session.scalars(
        select(ChatMessage).where(ChatMessage.user_id == user_id).order_by(ChatMessage.id.desc()).limit(limit)
    ))[::-1]
    while rows and rows[0].role != "user":  # діалог для API має починатися з user
        rows.pop(0)
    return [{"role": r.role, "content": r.content} for r in rows]


async def clear_history(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
    await session.commit()


async def requests_last_hour(session: AsyncSession, user_id: int) -> int:
    since = datetime.now() - timedelta(hours=1)
    return await session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.user_id == user_id, ChatMessage.role == "user", ChatMessage.created_at >= since
        )
    ) or 0


# ---------- заявки ----------
async def create_lead(session: AsyncSession, **kwargs) -> Lead:
    lead = Lead(**kwargs)
    session.add(lead)
    await session.commit()
    return lead


async def get_lead(session: AsyncSession, lead_id: int) -> Lead | None:
    return await session.get(Lead, lead_id)


async def leads_by_status(session: AsyncSession, status: LeadStatus, limit: int = 20) -> list[Lead]:
    return list(await session.scalars(
        select(Lead).where(Lead.status == status).order_by(Lead.id.desc()).limit(limit)
    ))


async def set_lead_status(session: AsyncSession, lead_id: int, status: LeadStatus) -> None:
    await session.execute(update(Lead).where(Lead.id == lead_id).values(status=status))
    await session.commit()


# ---------- статистика ----------
async def stats(session: AsyncSession) -> dict:
    day_ago = datetime.now() - timedelta(days=1)
    leads = dict((await session.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status))).all())
    tokens = (await session.execute(
        select(func.coalesce(func.sum(ChatMessage.input_tokens), 0), func.coalesce(func.sum(ChatMessage.output_tokens), 0))
    )).one()
    return {
        "users": await session.scalar(select(func.count(User.id))) or 0,
        "questions_24h": await session.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.role == "user", ChatMessage.created_at >= day_ago)
        ) or 0,
        "questions_total": await session.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.role == "user")) or 0,
        "leads": leads,
        "leads_24h": await session.scalar(select(func.count(Lead.id)).where(Lead.created_at >= day_ago)) or 0,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
    }
