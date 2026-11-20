"""Меню адмінки та статистика."""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...services.slots import now_local
from ...utils.render import render
from ...utils.text import MONTHS, money

router = Router(name="admin_menu")
MENU_TEXT = "🛠 <b>Адмін-панель</b>\nОберіть розділ:"


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(MENU_TEXT, reply_markup=akb.admin_menu())


@router.callback_query(AdminCb.filter(F.section == "menu"))
async def admin_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render(call, MENU_TEXT, akb.admin_menu())
    await call.answer()


@router.callback_query(AdminCb.filter(F.section == "stats"))
async def admin_stats(call: CallbackQuery, session: AsyncSession) -> None:
    now = now_local()
    s = await repo.stats(session, now)
    masters = "\n".join(f"  • {escape(n)}: {c}" for n, c in s["top_masters"]) or "  —"
    services = "\n".join(f"  • {escape(n)}: {c}" for n, c in s["top_services"]) or "  —"
    text = (
        f"📊 <b>Статистика — {MONTHS[now.month - 1]} {now.year}</b>\n\n"
        f"👥 Клієнтів у базі: <b>{s['clients']}</b>\n"
        f"📅 Майбутніх записів: <b>{s['upcoming']}</b>\n"
        f"✅ Виконано за місяць: <b>{s['done_month']}</b>\n"
        f"❌ Скасовано за місяць: {s['canceled_month']}\n"
        f"💰 Виручка за місяць: <b>{money(s['revenue_month'])}</b>\n\n"
        f"<b>Візити по майстрах:</b>\n{masters}\n\n<b>Популярні послуги:</b>\n{services}"
    )
    await render(call, text, akb.back_to_menu_kb())
    await call.answer()
