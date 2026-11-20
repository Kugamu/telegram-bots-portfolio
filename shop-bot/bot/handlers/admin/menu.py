"""Головне меню адмінки та статистика."""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...db.models import STATUS_LABELS
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...utils.render import render
from ...utils.text import money

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
    s = await repo.stats(session)
    by_status = "\n".join(f"  {label}: {s['by_status'].get(st, 0)}" for st, label in STATUS_LABELS.items())
    top = "\n".join(f"  {n}. {escape(name)} — {q} шт." for n, (name, q) in enumerate(s["top"], 1)) or "  поки немає продажів"
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Користувачів: <b>{s['users']}</b> (+{s['new_users_24h']} за добу)\n"
        f"📦 Товарів: <b>{s['products']}</b>, з них закінчилось: {s['out_of_stock']}\n"
        f"🧾 Замовлень за добу: <b>{s['orders_24h']}</b>\n\n"
        f"<b>Замовлення за статусами:</b>\n{by_status}\n\n"
        f"💰 Виручка (відправлені + виконані): <b>{money(s['revenue'])}</b>\n\n"
        f"🏆 <b>Топ-5 товарів:</b>\n{top}"
    )
    await render(call, text, akb.back_to_menu_kb())
    await call.answer()
