"""Шар доступу до даних."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Booking, BookingStatus, Master, Service, User, WorkingHours


# ---------- users ----------
async def upsert_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(id=tg_id, username=username, full_name=full_name)
        session.add(user)
    else:
        user.username, user.full_name, user.is_blocked = username, full_name, False
    await session.commit()
    return user


async def get_user(session: AsyncSession, tg_id: int) -> User | None:
    return await session.get(User, tg_id)


async def active_user_ids(session: AsyncSession) -> list[int]:
    return list(await session.scalars(select(User.id).where(User.is_blocked.is_(False))))


async def mark_blocked(session: AsyncSession, tg_id: int) -> None:
    await session.execute(update(User).where(User.id == tg_id).values(is_blocked=True))
    await session.commit()


# ---------- services ----------
async def list_services(session: AsyncSession, only_active: bool = True) -> list[Service]:
    stmt = select(Service).order_by(Service.id)
    if only_active:
        stmt = stmt.where(Service.is_active.is_(True))
    return list(await session.scalars(stmt))


async def get_service(session: AsyncSession, service_id: int) -> Service | None:
    return await session.get(Service, service_id)


async def count_bookings(session: AsyncSession, *, service_id: int | None = None, master_id: int | None = None) -> int:
    stmt = select(func.count(Booking.id))
    if service_id:
        stmt = stmt.where(Booking.service_id == service_id)
    if master_id:
        stmt = stmt.where(Booking.master_id == master_id)
    return await session.scalar(stmt) or 0


# ---------- masters ----------
async def list_masters(session: AsyncSession, only_active: bool = True) -> list[Master]:
    stmt = select(Master).order_by(Master.id)
    if only_active:
        stmt = stmt.where(Master.is_active.is_(True))
    return list(await session.scalars(stmt))


async def masters_for_service(session: AsyncSession, service_id: int) -> list[Master]:
    masters = await list_masters(session)
    return [m for m in masters if any(s.id == service_id for s in m.services)]


async def get_master(session: AsyncSession, master_id: int) -> Master | None:
    return await session.get(Master, master_id)


async def set_hours(session: AsyncSession, master: Master, weekday: int, start: time | None, end: time | None) -> None:
    """Встановлює години на день тижня; start=None — вихідний."""
    current = master.hours_for(weekday)
    if start is None:
        if current:
            master.hours.remove(current)
    elif current:
        current.start, current.end = start, end
    else:
        master.hours.append(WorkingHours(weekday=weekday, start=start, end=end))
    await session.commit()


# ---------- bookings ----------
async def bookings_in_range(session: AsyncSession, master_id: int, start: datetime, end: datetime) -> list[Booking]:
    rows = await session.scalars(
        select(Booking).where(
            Booking.master_id == master_id,
            Booking.status == BookingStatus.ACTIVE,
            Booking.start_at < end,
            Booking.end_at > start,
        )
    )
    return list(rows)


async def is_slot_free(session: AsyncSession, master_id: int, start: datetime, end: datetime) -> bool:
    return not await bookings_in_range(session, master_id, start, end)


async def create_booking(session: AsyncSession, **kwargs) -> Booking:
    booking = Booking(**kwargs)
    session.add(booking)
    await session.commit()
    await session.refresh(booking, ["master", "service"])
    return booking


async def get_booking(session: AsyncSession, booking_id: int) -> Booking | None:
    return await session.get(Booking, booking_id)


async def user_upcoming(session: AsyncSession, user_id: int, now: datetime) -> list[Booking]:
    rows = await session.scalars(
        select(Booking)
        .where(Booking.user_id == user_id, Booking.status == BookingStatus.ACTIVE, Booking.start_at > now)
        .order_by(Booking.start_at)
    )
    return list(rows)


async def bookings_between(session: AsyncSession, start: datetime, end: datetime) -> list[Booking]:
    rows = await session.scalars(
        select(Booking)
        .where(Booking.status == BookingStatus.ACTIVE, Booking.start_at >= start, Booking.start_at < end)
        .order_by(Booking.start_at)
    )
    return list(rows)


async def due_reminders(session: AsyncSession, now: datetime, hours: int) -> list[Booking]:
    rows = await session.scalars(
        select(Booking).where(
            Booking.status == BookingStatus.ACTIVE,
            Booking.reminded.is_(False),
            Booking.start_at > now,
            Booking.start_at <= now + timedelta(hours=hours),
        )
    )
    return list(rows)


async def close_finished(session: AsyncSession, now: datetime) -> int:
    """Записи, час яких минув, автоматично позначаються виконаними."""
    res = await session.execute(
        update(Booking)
        .where(Booking.status == BookingStatus.ACTIVE, Booking.end_at < now)
        .values(status=BookingStatus.DONE)
    )
    await session.commit()
    return res.rowcount or 0


# ---------- stats ----------
async def stats(session: AsyncSession, now: datetime) -> dict:
    month_start = datetime.combine(date(now.year, now.month, 1), time())
    done_month = (Booking.status == BookingStatus.DONE, Booking.start_at >= month_start)
    top_masters = (
        await session.execute(
            select(Master.name, func.count(Booking.id))
            .join(Booking, Booking.master_id == Master.id)
            .where(*done_month)
            .group_by(Master.name)
            .order_by(func.count(Booking.id).desc())
        )
    ).all()
    top_services = (
        await session.execute(
            select(Service.name, func.count(Booking.id))
            .join(Booking, Booking.service_id == Service.id)
            .where(Booking.status != BookingStatus.CANCELED, Booking.start_at >= month_start)
            .group_by(Service.name)
            .order_by(func.count(Booking.id).desc())
            .limit(5)
        )
    ).all()
    return {
        "clients": await session.scalar(select(func.count(User.id))) or 0,
        "upcoming": await session.scalar(
            select(func.count(Booking.id)).where(Booking.status == BookingStatus.ACTIVE, Booking.start_at > now)
        ) or 0,
        "done_month": await session.scalar(select(func.count(Booking.id)).where(*done_month)) or 0,
        "canceled_month": await session.scalar(
            select(func.count(Booking.id)).where(Booking.status == BookingStatus.CANCELED, Booking.start_at >= month_start)
        ) or 0,
        "revenue_month": await session.scalar(select(func.coalesce(func.sum(Booking.price), 0)).where(*done_month)) or 0,
        "top_masters": top_masters,
        "top_services": top_services,
    }
