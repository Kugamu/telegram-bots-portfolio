"""Перегляд записів за період, скасування адміністратором, позначка «виконано»."""
from datetime import datetime, time, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...db import repo
from ...db.models import BookingStatus
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...services.slots import now_local
from ...utils.render import render
from ...utils.text import booking_text, human_date

router = Router(name="admin_bookings")


def _period_range(period: str) -> tuple[datetime, datetime]:
    today = datetime.combine(now_local().date(), time())
    if period == "tomorrow":
        return today + timedelta(days=1), today + timedelta(days=2)
    if period == "week":
        return today, today + timedelta(days=7)
    return today, today + timedelta(days=1)


@router.callback_query(AdminCb.filter((F.section == "bk") & (F.action == "list")))
async def bk_periods(call: CallbackQuery) -> None:
    await render(call, "📋 <b>Записи</b>\nОберіть період:", akb.bookings_periods_kb())
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "bk") & (F.action == "period")))
async def bk_list(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    period = callback_data.value if callback_data.value in akb.PERIODS else "today"
    start, end = _period_range(period)
    bookings = (await repo.bookings_between(session, start, end))[:40]  # ліміт довжини повідомлення
    if bookings:
        # компактний розклад-текст, згрупований по днях
        lines, current_day = [], None
        for b in bookings:
            if b.start_at.date() != current_day:
                current_day = b.start_at.date()
                lines.append(f"\n<b>{human_date(current_day)}</b>")
            lines.append(f"{b.start_at:%H:%M} · {escape(b.master.name)} · {escape(b.service.name)} · {escape(b.client_name)}")
        body = "\n".join(lines)
    else:
        body = "\nЗаписів немає."
    await render(call, f"📋 <b>{akb.PERIODS[period]}</b>: {len(bookings)}\n{body}",
                 akb.bookings_list_kb(bookings, period))
    try:
        await call.answer()
    except TelegramBadRequest:  # уже відповіли в bk_set_status
        pass


@router.callback_query(AdminCb.filter((F.section == "bk") & (F.action == "view")))
async def bk_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    b = await repo.get_booking(session, callback_data.id)
    if b is None:
        return await call.answer("Запис не знайдено", show_alert=True)
    status = {BookingStatus.ACTIVE: "🟢 Активний", BookingStatus.DONE: "✅ Виконано", BookingStatus.CANCELED: "❌ Скасовано"}
    await render(call, f"{booking_text(b, for_admin=True)}\n\nСтатус: {status[b.status]}",
                 akb.booking_admin_kb(b, callback_data.value))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "bk") & (F.action.in_({"cancel", "done"}))))
async def bk_set_status(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, bot: Bot) -> None:
    b = await repo.get_booking(session, callback_data.id)
    if b is None or b.status is not BookingStatus.ACTIVE:
        return await call.answer("Запис уже не активний", show_alert=True)
    if callback_data.action == "cancel":
        b.status = BookingStatus.CANCELED
        await session.commit()
        try:
            await bot.send_message(
                b.user_id,
                f"😔 На жаль, ваш запис скасовано адміністратором:\n\n{booking_text(b)}\n\n"
                f"Оберіть інший час у «📅 Записатися» або зателефонуйте: {get_settings().business_phone}",
            )
        except TelegramAPIError:
            pass
        await call.answer("Запис скасовано, клієнта сповіщено")
    else:
        b.status = BookingStatus.DONE
        await session.commit()
        await call.answer("Позначено як виконаний")
    await bk_list(call, AdminCb(section="bk", action="period", value=callback_data.value), session)
