"""/start, головне меню, «Про магазин», «Мої замовлення», скасування будь-якого діалогу.

Роутер підключається першим, тому кнопки головного меню працюють з будь-якого FSM-стану
(користувач посеред оформлення натиснув «Каталог» — діалог коректно перерветься).
"""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..keyboards import user as kb
from ..utils.text import order_text

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    u = message.from_user
    await repo.upsert_user(session, u.id, u.username, u.full_name)
    shop = escape(get_settings().shop_name)
    await message.answer(
        f"Вітаємо в <b>{shop}</b>, {escape(u.first_name)}! ☕️\n\n"
        "Тут можна обрати свіжообсмажену каву, чай та аксесуари і оформити замовлення "
        "за хвилину — прямо в Telegram.\n\nОберіть розділ у меню нижче 👇",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text == kb.BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Дію скасовано. Ви в головному меню.", reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message, state: FSMContext) -> None:
    await state.clear()
    s = get_settings()
    await message.answer(
        f"<b>{escape(s.shop_name)}</b> — обсмажуємо каву щотижня 🔥\n\n"
        "🚚 Доставка Новою Поштою по всій Україні 1–2 дні\n"
        "💳 Оплата: переказ на карту або накладений платіж\n"
        "🕘 Підтримка: щодня 9:00–21:00\n\n"
        "Команди: /start — меню, /cancel — скасувати дію",
        reply_markup=kb.main_menu(),
    )


@router.message(F.text == kb.BTN_ORDERS)
async def my_orders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    orders = await repo.user_orders(session, message.from_user.id)
    if not orders:
        await message.answer("У вас ще немає замовлень. Час це виправити — загляньте в 🛍 Каталог!")
        return
    text = "\n\n➖➖➖➖➖\n\n".join(order_text(o) for o in orders[:5])
    await message.answer("<b>Ваші останні замовлення</b>\n\n" + text)
