"""Клавіатури клієнта."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from ..db.models import Booking, Master, Service
from ..utils.text import human_date, service_line
from .callbacks import BookCb, MyCb

BTN_BOOK = "📅 Записатися"
BTN_MY = "🗓 Мої записи"
BTN_PRICES = "💈 Послуги та ціни"
BTN_CONTACTS = "📍 Контакти"
BTN_CANCEL = "✖️ Скасувати"


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for t in (BTN_BOOK, BTN_MY, BTN_PRICES, BTN_CONTACTS):
        kb.button(text=t)
    kb.adjust(1, 2, 1)
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Оберіть дію")


def text_kb(*texts: str) -> ReplyKeyboardMarkup:
    """Reply-клавіатура з підказками + кнопка скасування."""
    rows = [[KeyboardButton(text=t)] for t in texts if t]
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def phone_kb(saved: str | None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="📱 Надіслати мій номер", request_contact=True)]]
    if saved:
        rows.insert(0, [KeyboardButton(text=saved)])
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def services_kb(services: list[Service]):
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(text=service_line(s), callback_data=BookCb(action="svc", sid=s.id))
    kb.adjust(1)
    return kb.as_markup()


def masters_kb(masters: list[Master], sid: int):
    kb = InlineKeyboardBuilder()
    for m in masters:
        kb.button(text=f"👤 {m.name}", callback_data=BookCb(action="mst", sid=sid, mid=m.id))
    kb.button(text="⬅️ До послуг", callback_data=BookCb(action="services"))
    kb.adjust(1)
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити запис", callback_data=MyCb(action="confirm"))
    kb.button(text="✖️ Скасувати", callback_data=MyCb(action="abort"))
    kb.adjust(1)
    return kb.as_markup()


def my_bookings_kb(bookings: list[Booking]):
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(text=f"❌ Скасувати: {human_date(b.start_at)} {b.start_at:%H:%M}", callback_data=MyCb(action="cancel", id=b.id))
    kb.adjust(1)
    return kb.as_markup()


def cancel_confirm_kb(booking_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="Так, скасувати", callback_data=MyCb(action="cancel_yes", id=booking_id))
    kb.button(text="Ні, залишити", callback_data=MyCb(action="keep", id=booking_id))
    kb.adjust(2)
    return kb.as_markup()


def reminder_kb(booking_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="👍 Буду", callback_data=MyCb(action="coming", id=booking_id))
    kb.button(text="❌ Скасувати", callback_data=MyCb(action="cancel", id=booking_id))
    kb.adjust(2)
    return kb.as_markup()
