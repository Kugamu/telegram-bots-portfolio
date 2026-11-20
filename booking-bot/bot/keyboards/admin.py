"""Клавіатури адмін-панелі."""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..db.models import Booking, Master, Service
from ..utils.text import WEEKDAYS_FULL, money
from .callbacks import AdminCb


def _back(kb: InlineKeyboardBuilder, cb: AdminCb, text: str = "⬅️ Назад") -> None:
    kb.button(text=text, callback_data=cb)


def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Записи", callback_data=AdminCb(section="bk"))
    kb.button(text="💈 Послуги", callback_data=AdminCb(section="svc"))
    kb.button(text="👤 Майстри", callback_data=AdminCb(section="mst"))
    kb.button(text="📊 Статистика", callback_data=AdminCb(section="stats"))
    kb.button(text="📣 Розсилка", callback_data=AdminCb(section="mail"))
    kb.adjust(1, 2, 2)
    return kb.as_markup()


def back_to_menu_kb():
    kb = InlineKeyboardBuilder()
    _back(kb, AdminCb(section="menu"), "⬅️ В адмін-меню")
    return kb.as_markup()


# ---------- записи ----------
PERIODS = {"today": "Сьогодні", "tomorrow": "Завтра", "week": "Найближчі 7 днів"}


def bookings_periods_kb():
    kb = InlineKeyboardBuilder()
    for key, title in PERIODS.items():
        kb.button(text=title, callback_data=AdminCb(section="bk", action="period", value=key))
    _back(kb, AdminCb(section="menu"))
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def bookings_list_kb(bookings: list[Booking], period: str):
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(text=f"{b.start_at:%d.%m %H:%M} · {b.master.name} · {b.client_name[:15]}",
                  callback_data=AdminCb(section="bk", action="view", id=b.id, value=period))
    _back(kb, AdminCb(section="bk"))
    kb.adjust(1)
    return kb.as_markup()


def booking_admin_kb(b: Booking, period: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Скасувати (сповістити клієнта)", callback_data=AdminCb(section="bk", action="cancel", id=b.id, value=period))
    kb.button(text="✅ Позначити виконаним", callback_data=AdminCb(section="bk", action="done", id=b.id, value=period))
    _back(kb, AdminCb(section="bk", action="period", value=period), "⬅️ До списку")
    kb.adjust(1)
    return kb.as_markup()


# ---------- послуги ----------
def services_admin_kb(services: list[Service]):
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(text=("" if s.is_active else "🙈 ") + f"{s.name} · {money(s.price)}",
                  callback_data=AdminCb(section="svc", action="view", id=s.id))
    kb.button(text="➕ Нова послуга", callback_data=AdminCb(section="svc", action="new"))
    _back(kb, AdminCb(section="menu"))
    kb.adjust(1)
    return kb.as_markup()


SERVICE_FIELDS = {"name": "✏️ Назва", "price": "💰 Ціна", "duration": "⏱ Тривалість"}


def service_admin_kb(s: Service):
    kb = InlineKeyboardBuilder()
    for field, title in SERVICE_FIELDS.items():
        kb.button(text=title, callback_data=AdminCb(section="svc", action="edit", id=s.id, value=field))
    kb.button(text="🙈 Приховати" if s.is_active else "👁 Показати", callback_data=AdminCb(section="svc", action="toggle", id=s.id))
    kb.button(text="🗑 Видалити", callback_data=AdminCb(section="svc", action="delete", id=s.id))
    _back(kb, AdminCb(section="svc"))
    kb.adjust(3, 2, 1)
    return kb.as_markup()


# ---------- майстри ----------
def masters_admin_kb(masters: list[Master]):
    kb = InlineKeyboardBuilder()
    for m in masters:
        kb.button(text=("" if m.is_active else "🙈 ") + m.name, callback_data=AdminCb(section="mst", action="view", id=m.id))
    kb.button(text="➕ Новий майстер", callback_data=AdminCb(section="mst", action="new"))
    _back(kb, AdminCb(section="menu"))
    kb.adjust(1)
    return kb.as_markup()


def master_admin_kb(m: Master):
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Ім'я", callback_data=AdminCb(section="mst", action="edit", id=m.id, value="name"))
    kb.button(text="📝 Опис", callback_data=AdminCb(section="mst", action="edit", id=m.id, value="description"))
    kb.button(text="💈 Послуги", callback_data=AdminCb(section="mst", action="services", id=m.id))
    kb.button(text="🕒 Графік", callback_data=AdminCb(section="mst", action="schedule", id=m.id))
    kb.button(text="🙈 Приховати" if m.is_active else "👁 Показати", callback_data=AdminCb(section="mst", action="toggle", id=m.id))
    kb.button(text="🗑 Видалити", callback_data=AdminCb(section="mst", action="delete", id=m.id))
    _back(kb, AdminCb(section="mst"))
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def master_services_kb(m: Master, services: list[Service]):
    kb = InlineKeyboardBuilder()
    own = {s.id for s in m.services}
    for s in services:
        mark = "✅" if s.id in own else "▫️"
        kb.button(text=f"{mark} {s.name}", callback_data=AdminCb(section="mst", action="svc_toggle", id=m.id, value=str(s.id)))
    _back(kb, AdminCb(section="mst", action="view", id=m.id), "⬅️ Готово")
    kb.adjust(1)
    return kb.as_markup()


def master_schedule_kb(m: Master):
    kb = InlineKeyboardBuilder()
    for wd, name in enumerate(WEEKDAYS_FULL):
        h = m.hours_for(wd)
        label = f"{h.start:%H:%M}–{h.end:%H:%M}" if h else "вихідний"
        kb.button(text=f"{name}: {label}", callback_data=AdminCb(section="mst", action="day", id=m.id, value=str(wd)))
    _back(kb, AdminCb(section="mst", action="view", id=m.id), "⬅️ Готово")
    kb.adjust(1)
    return kb.as_markup()


def confirm_delete_kb(section: str, obj_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Так, видалити", callback_data=AdminCb(section=section, action="delete_yes", id=obj_id))
    kb.button(text="Ні", callback_data=AdminCb(section=section, action="view", id=obj_id))
    kb.adjust(2)
    return kb.as_markup()


def broadcast_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Надіслати всім", callback_data=AdminCb(section="mail", action="send"))
    kb.button(text="✖️ Скасувати", callback_data=AdminCb(section="mail", action="cancel"))
    kb.adjust(1)
    return kb.as_markup()
