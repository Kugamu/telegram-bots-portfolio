"""Клавіатури та CallbackData."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from ..db.models import LEAD_LABELS, Lead, LeadStatus

BTN_PRICES = "💰 Скільки коштує ремонт?"
BTN_TERMS = "⏱ Які терміни?"
BTN_LEAD = "📝 Залишити заявку"
BTN_RESET = "🔄 Новий діалог"
BTN_CANCEL = "✖️ Скасувати"
QUICK_QUESTIONS = {BTN_PRICES, BTN_TERMS}


class LeadCb(CallbackData, prefix="lead"):
    action: str  # start


class AdminCb(CallbackData, prefix="adm"):
    section: str  # menu | leads | stats | kb
    action: str = "list"
    id: int = 0
    value: str = ""


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for t in (BTN_PRICES, BTN_TERMS, BTN_LEAD, BTN_RESET):
        kb.button(text=t)
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Поставте запитання…")


def cancel_kb(*hints: str) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=h)] for h in hints if h]
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Надіслати мій номер", request_contact=True)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def lead_offer_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Залишити заявку", callback_data=LeadCb(action="start"))
    return kb.as_markup()


# ---------- адмінка ----------
def admin_menu(new_leads: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"📋 Заявки ({new_leads} нових)", callback_data=AdminCb(section="leads"))
    kb.button(text="📊 Статистика", callback_data=AdminCb(section="stats"))
    kb.button(text="🔄 Оновити базу знань", callback_data=AdminCb(section="kb"))
    kb.adjust(1)
    return kb.as_markup()


def leads_filter_kb(counts: dict):
    kb = InlineKeyboardBuilder()
    for st, label in LEAD_LABELS.items():
        kb.button(text=f"{label} ({counts.get(st, 0)})", callback_data=AdminCb(section="leads", action="status", value=st.value))
    kb.button(text="⬅️ Назад", callback_data=AdminCb(section="menu"))
    kb.adjust(1)
    return kb.as_markup()


def leads_list_kb(leads: list[Lead], status: LeadStatus):
    kb = InlineKeyboardBuilder()
    for lead in leads:
        kb.button(text=f"#{lead.id} · {lead.name[:20]} · {lead.created_at:%d.%m %H:%M}",
                  callback_data=AdminCb(section="leads", action="view", id=lead.id, value=status.value))
    kb.button(text="⬅️ Назад", callback_data=AdminCb(section="leads"))
    kb.adjust(1)
    return kb.as_markup()


def lead_admin_kb(lead: Lead, with_back: bool = True):
    kb = InlineKeyboardBuilder()
    for st, label in LEAD_LABELS.items():
        if st is not lead.status:
            kb.button(text=f"→ {label}", callback_data=AdminCb(section="leads", action="set", id=lead.id, value=st.value))
    if with_back:
        kb.button(text="⬅️ До списку", callback_data=AdminCb(section="leads", action="status", value=lead.status.value))
    kb.adjust(2, 1)
    return kb.as_markup()


def back_to_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В адмін-меню", callback_data=AdminCb(section="menu"))
    return kb.as_markup()
