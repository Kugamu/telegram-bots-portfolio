"""Бізнес-логіка розкладу: розрахунок вільних слотів з урахуванням графіка майстра,
тривалості послуги, вже існуючих записів і мінімального часу до запису."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..db.models import Booking, Master, Service


def now_local() -> datetime:
    """Поточний час у часовому поясі салону (naive, як і в БД)."""
    return datetime.now(get_settings().tz).replace(tzinfo=None)


def _free_slots_for_day(
    master: Master, service: Service, day: date, bookings: list[Booking], now: datetime
) -> list[time]:
    s = get_settings()
    hours = master.hours_for(day.weekday())
    if hours is None:
        return []
    earliest = now + timedelta(minutes=s.min_lead_min)
    duration = timedelta(minutes=service.duration_min)
    step = timedelta(minutes=s.slot_step_min)

    slot = datetime.combine(day, hours.start)
    day_end = datetime.combine(day, hours.end)
    result = []
    while slot + duration <= day_end:
        slot_end = slot + duration
        if slot >= earliest and not any(b.start_at < slot_end and b.end_at > slot for b in bookings):
            result.append(slot.time())
        slot += step
    return result


def last_bookable_day(now: datetime) -> date:
    return now.date() + timedelta(days=get_settings().booking_days_ahead)


async def free_slots(session: AsyncSession, master: Master, service: Service, day: date) -> list[time]:
    now = now_local()
    if not now.date() <= day <= last_bookable_day(now):
        return []
    start = datetime.combine(day, time())
    bookings = await repo.bookings_in_range(session, master.id, start, start + timedelta(days=1))
    return _free_slots_for_day(master, service, day, bookings, now)


async def available_days(session: AsyncSession, master: Master, service: Service, year: int, month: int) -> set[int]:
    """Дні місяця, в які є хоча б один вільний слот. Один запит до БД на весь місяць."""
    now = now_local()
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    lo, hi = max(first, now.date()), min(last, last_bookable_day(now))
    if lo > hi:
        return set()
    bookings = await repo.bookings_in_range(
        session, master.id, datetime.combine(lo, time()), datetime.combine(hi + timedelta(days=1), time())
    )
    days = set()
    d = lo
    while d <= hi:
        day_bookings = [b for b in bookings if b.start_at.date() == d]
        if _free_slots_for_day(master, service, d, day_bookings, now):
            days.add(d.day)
        d += timedelta(days=1)
    return days
