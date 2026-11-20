"""Адмінка: заявки (зі статусами), статистика використання AI, гаряче оновлення бази знань."""
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import LEAD_LABELS, Lead, LeadStatus
from ..filters import IsAdmin
from ..keyboards import kb
from ..keyboards.kb import AdminCb
from ..services.ai import AIConsultant
from ..utils.render import render

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def _counts(session: AsyncSession) -> dict:
    return dict((await session.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status))).all())


def _lead_text(lead: Lead) -> str:
    return (f"<b>Заявка №{lead.id}</b> · {LEAD_LABELS[lead.status]}\n🗓 {lead.created_at:%d.%m.%Y %H:%M}\n\n"
            f"👤 {escape(lead.name)}\n📞 {lead.phone}\n🆔 <a href=\"tg://user?id={lead.user_id}\">написати клієнту</a>\n\n"
            f"📝 {escape(lead.request)}")


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    counts = await _counts(session)
    await message.answer("🛠 <b>Адмін-панель</b>", reply_markup=kb.admin_menu(counts.get(LeadStatus.NEW, 0)))


@router.callback_query(AdminCb.filter(F.section == "menu"))
async def admin_menu(call: CallbackQuery, session: AsyncSession) -> None:
    counts = await _counts(session)
    await render(call, "🛠 <b>Адмін-панель</b>", kb.admin_menu(counts.get(LeadStatus.NEW, 0)))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "leads") & (F.action == "list")))
async def leads_filters(call: CallbackQuery, session: AsyncSession) -> None:
    await render(call, "📋 <b>Заявки</b>", kb.leads_filter_kb(await _counts(session)))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "leads") & (F.action == "status")))
async def leads_list(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    try:
        status = LeadStatus(callback_data.value)
    except ValueError:
        return await call.answer("Невідомий статус", show_alert=True)
    leads = await repo.leads_by_status(session, status)
    await render(call, f"📋 {LEAD_LABELS[status]}: {len(leads)}" + ("" if leads else "\n\nПорожньо."),
                 kb.leads_list_kb(leads, status))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "leads") & (F.action == "view")))
async def lead_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    lead = await repo.get_lead(session, callback_data.id)
    if lead is None:
        return await call.answer("Заявку не знайдено", show_alert=True)
    await render(call, _lead_text(lead), kb.lead_admin_kb(lead))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "leads") & (F.action == "set")))
async def lead_set(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, bot: Bot) -> None:
    lead = await repo.get_lead(session, callback_data.id)
    if lead is None:
        return await call.answer("Заявку не знайдено", show_alert=True)
    lead.status = LeadStatus(callback_data.value)
    await session.commit()
    await call.answer(f"Статус: {LEAD_LABELS[lead.status]}")
    # повідомлення-сповіщення (без кнопки «назад») оновлюємо лише клавіатуру, щоб не загубити контекст діалогу
    try:
        if call.message.text and call.message.text.startswith("🔥"):
            await call.message.edit_reply_markup(reply_markup=kb.lead_admin_kb(lead, with_back=False))
        else:
            await render(call, _lead_text(lead), kb.lead_admin_kb(lead))
    except TelegramBadRequest:
        pass


@router.callback_query(AdminCb.filter(F.section == "stats"))
async def admin_stats(call: CallbackQuery, session: AsyncSession) -> None:
    s = await repo.stats(session)
    leads = "\n".join(f"  {label}: {s['leads'].get(st, 0)}" for st, label in LEAD_LABELS.items())
    total_leads = sum(s["leads"].values())
    conversion = f"{total_leads / s['users'] * 100:.0f}%" if s["users"] else "—"
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Користувачів: <b>{s['users']}</b>\n"
        f"💬 Запитань до AI: <b>{s['questions_total']}</b> (за добу: {s['questions_24h']})\n"
        f"📝 Заявок за добу: <b>{s['leads_24h']}</b>\n"
        f"🎯 Конверсія користувач → заявка: <b>{conversion}</b>\n\n"
        f"<b>Заявки:</b>\n{leads}\n\n"
        f"🔢 Токени Claude: вхід {s['input_tokens']:,} / вихід {s['output_tokens']:,}".replace(",", " ")
    )
    await render(call, text, kb.back_to_menu_kb())
    await call.answer()


@router.callback_query(AdminCb.filter(F.section == "kb"))
async def reload_kb(call: CallbackQuery, ai: AIConsultant) -> None:
    size = ai.reload_knowledge()
    await call.answer(f"✅ Базу знань перечитано ({size} символів)", show_alert=True)
