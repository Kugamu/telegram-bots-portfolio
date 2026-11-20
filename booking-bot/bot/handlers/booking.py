"""Сценарій запису: послуга → майстер → дата (календар) → час → ім'я → телефон → підтвердження."""
import logging
import re
from datetime import date, datetime, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..keyboards import user as kb
from ..keyboards.calendar import calendar_kb, slots_kb
from ..keyboards.callbacks import BookCb, MyCb
from ..services import slots as sl
from ..services.notify import notify_admins
from ..states import BookingSG
from ..utils.render import render
from ..utils.text import booking_text, duration, human_date, money

router = Router(name="booking")
log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{10,18}$")


def normalize_phone(raw: str) -> str | None:
    if not PHONE_RE.match(raw.strip()):
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    return "+" + digits if 11 <= len(digits) <= 15 else None


async def _ack(call: CallbackQuery) -> None:
    """Відповідь на callback, яка не падає, якщо на нього вже відповіли (алерт вище по стеку)."""
    try:
        await call.answer()
    except TelegramBadRequest:
        pass


def _parse_ymd(ymd: str) -> date | None:
    try:
        return datetime.strptime(ymd, "%Y%m%d").date()
    except ValueError:
        return None


async def _load(session: AsyncSession, call: CallbackQuery, sid: int, mid: int = 0):
    """Дістає послугу й майстра з БД; якщо їх видалили/приховали — показує алерт."""
    service = await repo.get_service(session, sid)
    if service is None or not service.is_active:
        await call.answer("Ця послуга більше недоступна. Почніть запис заново.", show_alert=True)
        return None, None
    if not mid:
        return service, None
    master = await repo.get_master(session, mid)
    if master is None or not master.is_active or service not in master.services:
        await call.answer("Цей майстер зараз недоступний. Оберіть іншого.", show_alert=True)
        return None, None
    return service, master


# ---------- 1. послуга ----------
SERVICES_TEXT = "📅 <b>Запис</b>\n\nКрок 1/4. Оберіть послугу:"


@router.message(F.text == kb.BTN_BOOK)
async def book_entry(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    u = message.from_user
    await repo.upsert_user(session, u.id, u.username, u.full_name)
    services = await repo.list_services(session)
    if not services:
        await message.answer("Запис тимчасово недоступний — послуги ще не налаштовані.")
        return
    await message.answer(SERVICES_TEXT, reply_markup=kb.services_kb(services))


@router.callback_query(BookCb.filter(F.action == "services"))
async def book_services(call: CallbackQuery, session: AsyncSession) -> None:
    await render(call, SERVICES_TEXT, kb.services_kb(await repo.list_services(session)))
    await call.answer()


# ---------- 2. майстер ----------
@router.callback_query(BookCb.filter(F.action == "svc"))
async def book_service(call: CallbackQuery, callback_data: BookCb, session: AsyncSession) -> None:
    service, _ = await _load(session, call, callback_data.sid)
    if service is None:
        return
    masters = await repo.masters_for_service(session, service.id)
    if not masters:
        await call.answer("На жаль, зараз немає майстрів для цієї послуги", show_alert=True)
        return
    lines = "\n".join(f"👤 <b>{escape(m.name)}</b> — {escape(m.description)}" for m in masters)
    await render(
        call,
        f"<b>{escape(service.name)}</b> · {duration(service.duration_min)} · {money(service.price)}\n\n"
        f"Крок 2/4. Оберіть майстра:\n\n{lines}",
        kb.masters_kb(masters, service.id),
    )
    await call.answer()


# ---------- 3. дата ----------
async def _show_calendar(call: CallbackQuery, session: AsyncSession, sid: int, mid: int, month_start: date) -> None:
    service, master = await _load(session, call, sid, mid)
    if service is None:
        return
    now = sl.now_local()
    last = sl.last_bookable_day(now)
    # не даємо гортати в минуле або далі ніж дозволено
    month_start = min(max(month_start, now.date().replace(day=1)), last.replace(day=1))
    days = await sl.available_days(session, master, service, month_start.year, month_start.month)
    has_prev = month_start > now.date().replace(day=1)
    has_next = month_start < last.replace(day=1)
    hint = "" if days else "\n\n😔 У цьому місяці вільних місць немає — гляньте наступний."
    await render(
        call,
        f"<b>{escape(service.name)}</b> · майстер {escape(master.name)}\n\n"
        f"Крок 3/4. Оберіть дату (доступні дні — з числами):{hint}",
        calendar_kb(month_start.year, month_start.month, days, service.id, master.id, has_prev, has_next),
    )
    await _ack(call)


@router.callback_query(BookCb.filter(F.action == "mst"))
async def book_master(call: CallbackQuery, callback_data: BookCb, session: AsyncSession) -> None:
    await _show_calendar(call, session, callback_data.sid, callback_data.mid, sl.now_local().date().replace(day=1))


@router.callback_query(BookCb.filter(F.action == "cal"))
async def book_calendar_nav(call: CallbackQuery, callback_data: BookCb, session: AsyncSession) -> None:
    month_start = _parse_ymd(callback_data.ymd) or sl.now_local().date().replace(day=1)
    await _show_calendar(call, session, callback_data.sid, callback_data.mid, month_start)


@router.callback_query(BookCb.filter(F.action == "ign"))
async def book_ignore(call: CallbackQuery) -> None:
    await call.answer()


# ---------- 4. час ----------
@router.callback_query(BookCb.filter(F.action == "day"))
async def book_day(call: CallbackQuery, callback_data: BookCb, session: AsyncSession) -> None:
    service, master = await _load(session, call, callback_data.sid, callback_data.mid)
    day = _parse_ymd(callback_data.ymd)
    if service is None or day is None:
        return
    free = await sl.free_slots(session, master, service, day)
    if not free:
        await call.answer("На цей день вільних місць уже немає", show_alert=True)
        return await _show_calendar(call, session, service.id, master.id, day.replace(day=1))
    await render(
        call,
        f"<b>{escape(service.name)}</b> · майстер {escape(master.name)}\n📅 {human_date(day)}\n\nКрок 4/4. Оберіть час:",
        slots_kb(free, service.id, master.id, day),
    )
    await _ack(call)


@router.callback_query(BookCb.filter(F.action == "slot"))
async def book_slot(call: CallbackQuery, callback_data: BookCb, session: AsyncSession, state: FSMContext) -> None:
    service, master = await _load(session, call, callback_data.sid, callback_data.mid)
    if service is None:
        return
    try:
        start = datetime.strptime(callback_data.ymd + callback_data.hm, "%Y%m%d%H%M")
    except ValueError:
        return await call.answer("Некоректний час", show_alert=True)
    # слот міг зайняти хтось інший, поки клієнт думав
    if start.time() not in await sl.free_slots(session, master, service, start.date()):
        await call.answer("Цей час щойно зайняли 😔 Оберіть інший.", show_alert=True)
        return await book_day(call, BookCb(action="day", sid=service.id, mid=master.id, ymd=callback_data.ymd), session)

    await state.set_state(BookingSG.name)
    await state.update_data(sid=service.id, mid=master.id, start=start.isoformat())
    user = await repo.get_user(session, call.from_user.id)
    suggestion = (user.saved_name if user and user.saved_name else call.from_user.first_name)[:60]
    await call.message.answer(
        f"Чудово! {human_date(start)} о <b>{start:%H:%M}</b> ✨\n\nЯк до вас звертатися?",
        reply_markup=kb.text_kb(suggestion),
    )
    await call.answer()


# ---------- контакти ----------
@router.message(BookingSG.name, F.text)
async def book_name(message: Message, session: AsyncSession, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 60:
        return await message.answer("Ім'я має містити від 2 до 60 символів.")
    await state.update_data(name=name)
    await state.set_state(BookingSG.phone)
    user = await repo.get_user(session, message.from_user.id)
    await message.answer("📞 Ваш номер телефону? Натисніть кнопку або введіть вручну:",
                         reply_markup=kb.phone_kb(user.phone if user else None))


@router.message(BookingSG.phone, F.contact)
@router.message(BookingSG.phone, F.text)
async def book_phone(message: Message, session: AsyncSession, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    if not raw.startswith(("+", "0")):
        raw = "+" + raw
    phone = normalize_phone(raw)
    if phone is None:
        return await message.answer("Номер виглядає некоректно 🤔 Приклад: <code>+380671234567</code>")
    await state.update_data(phone=phone)
    await state.set_state(BookingSG.confirm)
    data = await state.get_data()
    service = await repo.get_service(session, data["sid"])
    master = await repo.get_master(session, data["mid"])
    start = datetime.fromisoformat(data["start"])
    await message.answer("Майже готово!", reply_markup=kb.main_menu())
    await message.answer(
        "<b>Перевірте запис:</b>\n\n"
        f"💈 {escape(service.name)}\n👤 Майстер: {escape(master.name)}\n"
        f"📅 {human_date(start)}, <b>{start:%H:%M}</b>\n⏱ {duration(service.duration_min)}\n"
        f"💰 {money(service.price)}\n\n🙋 {escape(data['name'])}\n📞 {phone}",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(BookingSG.confirm, MyCb.filter(F.action == "confirm"))
async def book_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    service, master = await _load(session, call, data["sid"], data["mid"])
    if service is None:
        return
    start = datetime.fromisoformat(data["start"])
    end = start + timedelta(minutes=service.duration_min)
    # фінальна перевірка — захист від подвійного бронювання
    if start <= sl.now_local() or not await repo.is_slot_free(session, master.id, start, end):
        await call.message.edit_text("😔 На жаль, цей час уже зайнятий. Будь ласка, оберіть інший.",
                                     reply_markup=None)
        return await call.answer()

    booking = await repo.create_booking(
        session, user_id=call.from_user.id, master_id=master.id, service_id=service.id,
        start_at=start, end_at=end, client_name=data["name"], phone=data["phone"], price=service.price,
    )
    user = await repo.get_user(session, call.from_user.id)
    if user:
        user.saved_name, user.phone = data["name"], data["phone"]
        await session.commit()

    await call.message.edit_text(
        f"✅ <b>Ви записані!</b>\n\n{booking_text(booking)}\n\n"
        "Я нагадаю про візит заздалегідь. Переглянути чи скасувати запис — «🗓 Мої записи»."
    )
    await call.answer("Запис створено!")
    log.info("Booking #%s created by %s", booking.id, call.from_user.id)
    await notify_admins(bot, "🆕 <b>Новий запис</b>\n\n" + booking_text(booking, for_admin=True))


@router.callback_query(MyCb.filter(F.action.in_({"confirm", "abort"})))
async def book_abort_or_stale(call: CallbackQuery, callback_data: MyCb, state: FSMContext) -> None:
    if callback_data.action == "abort":
        await state.clear()
        await call.message.edit_text("Запис скасовано. Можете почати знову через «📅 Записатися».")
        return await call.answer()
    await call.answer("Ця кнопка вже неактуальна. Почніть запис заново.", show_alert=True)


@router.message(BookingSG.confirm)
async def book_expect_button(message: Message) -> None:
    await message.answer("Підтвердьте запис кнопкою вище 👆 або натисніть /cancel.")


@router.message(BookingSG.name)
@router.message(BookingSG.phone)
async def book_expect_text(message: Message) -> None:
    await message.answer("Очікую текстову відповідь 🙂 Або /cancel, щоб скасувати.")
