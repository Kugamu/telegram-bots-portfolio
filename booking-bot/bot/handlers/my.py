"""«Мої записи»: перегляд майбутніх записів, скасування, відповідь на нагадування."""
from datetime import timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..db.models import BookingStatus
from ..keyboards import user as kb
from ..keyboards.callbacks import MyCb
from ..services.notify import notify_admins
from ..services.slots import now_local
from ..utils.render import render
from ..utils.text import booking_text

router = Router(name="my")


async def _my_view(session: AsyncSession, user_id: int):
    bookings = await repo.user_upcoming(session, user_id, now_local())
    if not bookings:
        return "У вас немає активних записів. Натисніть «📅 Записатися» 🙂", None
    body = "\n\n➖➖➖\n\n".join(booking_text(b) for b in bookings)
    return f"🗓 <b>Ваші записи</b>\n\n{body}", kb.my_bookings_kb(bookings)


@router.message(F.text == kb.BTN_MY)
async def my_bookings(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _my_view(session, message.from_user.id)
    await message.answer(text, reply_markup=markup)


async def _get_own_active(call: CallbackQuery, session: AsyncSession, booking_id: int):
    b = await repo.get_booking(session, booking_id)
    if b is None or b.user_id != call.from_user.id or b.status is not BookingStatus.ACTIVE:
        await call.answer("Цей запис уже неактивний.", show_alert=True)
        return None
    return b


@router.callback_query(MyCb.filter(F.action == "cancel"))
async def cancel_ask(call: CallbackQuery, callback_data: MyCb, session: AsyncSession) -> None:
    b = await _get_own_active(call, session, callback_data.id)
    if b is None:
        return
    s = get_settings()
    if b.start_at - now_local() < timedelta(hours=s.cancel_min_hours):
        await call.answer(
            f"До візиту менше {s.cancel_min_hours} год — скасувати можна лише за телефоном {s.business_phone}",
            show_alert=True,
        )
        return
    await render(call, f"Скасувати запис?\n\n{booking_text(b)}", kb.cancel_confirm_kb(b.id))
    await call.answer()


@router.callback_query(MyCb.filter(F.action == "cancel_yes"))
async def cancel_yes(call: CallbackQuery, callback_data: MyCb, session: AsyncSession, bot: Bot) -> None:
    b = await _get_own_active(call, session, callback_data.id)
    if b is None:
        return
    b.status = BookingStatus.CANCELED
    await session.commit()
    await render(call, "✅ Запис скасовано. Будемо раді бачити вас іншим разом!")
    await call.answer()
    await notify_admins(bot, "❌ <b>Клієнт скасував запис</b>\n\n" + booking_text(b, for_admin=True))


@router.callback_query(MyCb.filter(F.action == "keep"))
async def cancel_keep(call: CallbackQuery, session: AsyncSession) -> None:
    text, markup = await _my_view(session, call.from_user.id)
    await render(call, text, markup)
    await call.answer("Запис залишено 👍")


@router.callback_query(MyCb.filter(F.action == "coming"))
async def reminder_coming(call: CallbackQuery, callback_data: MyCb, session: AsyncSession) -> None:
    b = await _get_own_active(call, session, callback_data.id)
    if b is None:
        return
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"Дякуємо, {escape(b.client_name)}! Чекаємо на вас о {b.start_at:%H:%M} ✂️")
    await call.answer()
