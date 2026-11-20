"""Inline-календар: місячна сітка, де можна натиснути лише дні з вільними слотами."""
import calendar
from datetime import date, time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..utils.text import MONTHS, WEEKDAYS
from .callbacks import BookCb

EMPTY = "⠀"  # невидимий символ: Telegram не приймає порожній текст кнопки


def _btn(text: str, cb: BookCb) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def calendar_kb(
    year: int, month: int, available: set[int], sid: int, mid: int, has_prev: bool, has_next: bool
) -> InlineKeyboardMarkup:
    ign = BookCb(action="ign")
    rows = [[_btn(f"{MONTHS[month - 1]} {year}", ign)], [_btn(d, ign) for d in WEEKDAYS]]

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(_btn(EMPTY, ign))
            elif day in available:
                row.append(_btn(str(day), BookCb(action="day", sid=sid, mid=mid, ymd=f"{year:04d}{month:02d}{day:02d}")))
            else:
                row.append(_btn("·", ign))
        rows.append(row)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    rows.append([
        _btn("◀️", BookCb(action="cal", sid=sid, mid=mid, ymd=f"{prev_y:04d}{prev_m:02d}01")) if has_prev else _btn(EMPTY, ign),
        _btn("⬅️ Майстри", BookCb(action="svc", sid=sid)),
        _btn("▶️", BookCb(action="cal", sid=sid, mid=mid, ymd=f"{next_y:04d}{next_m:02d}01")) if has_next else _btn(EMPTY, ign),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def slots_kb(slots: list[time], sid: int, mid: int, day: date) -> InlineKeyboardMarkup:
    ymd = day.strftime("%Y%m%d")
    rows, row = [], []
    for t in slots:
        row.append(_btn(t.strftime("%H:%M"), BookCb(action="slot", sid=sid, mid=mid, ymd=ymd, hm=t.strftime("%H%M"))))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("⬅️ До календаря", BookCb(action="cal", sid=sid, mid=mid, ymd=day.strftime("%Y%m01")))])
    return InlineKeyboardMarkup(inline_keyboard=rows)
