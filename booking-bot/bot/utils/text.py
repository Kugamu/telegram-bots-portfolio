"""Форматування текстів."""
from datetime import date, datetime
from html import escape

from ..db.models import Booking, Master, Service

MONTHS = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
          "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]
MONTHS_GEN = ["січня", "лютого", "березня", "квітня", "травня", "червня",
              "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
WEEKDAYS_FULL = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]


def money(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " ₴"


def human_date(d: date | datetime) -> str:
    return f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS_GEN[d.month - 1]}"


def duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return " ".join(p for p in (f"{h} год" if h else "", f"{m} хв" if m else "") if p)


def service_line(s: Service) -> str:
    return f"{s.name} · {duration(s.duration_min)} · {money(s.price)}"


def booking_text(b: Booking, for_admin: bool = False) -> str:
    text = (
        f"<b>{escape(b.service.name)}</b>\n"
        f"📅 {human_date(b.start_at)}, <b>{b.start_at:%H:%M}</b>–{b.end_at:%H:%M}\n"
        f"👤 Майстер: {escape(b.master.name)}\n"
        f"💰 {money(b.price)}"
    )
    if for_admin:
        text += f"\n\n🙋 {escape(b.client_name)}\n📞 {escape(b.phone)}\n🆔 <code>{b.user_id}</code> · запис #{b.id}"
    return text


def schedule_text(m: Master) -> str:
    lines = []
    for wd, name in enumerate(WEEKDAYS_FULL):
        h = m.hours_for(wd)
        lines.append(f"{name}: " + (f"{h.start:%H:%M}–{h.end:%H:%M}" if h else "вихідний"))
    return "\n".join(lines)
