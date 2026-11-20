"""Кошик: перегляд, зміна кількості, видалення, очищення."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..keyboards import user as kb
from ..keyboards.callbacks import CartCb
from ..utils.render import render
from ..utils.text import cart_text

router = Router(name="cart")


async def _cart_view(session: AsyncSession, user_id: int):
    items = await repo.get_cart(session, user_id)
    return cart_text(items), (kb.cart_kb(items) if items else None)


@router.message(F.text == kb.BTN_CART)
async def cart_entry(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _cart_view(session, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(CartCb.filter(F.action == "show"))
async def cart_show(call: CallbackQuery, session: AsyncSession) -> None:
    text, markup = await _cart_view(session, call.from_user.id)
    await render(call, text, markup)
    await call.answer()


@router.callback_query(CartCb.filter(F.action == "noop"))
async def cart_noop(call: CallbackQuery) -> None:
    await call.answer("Змініть кількість кнопками ➖ / ➕")


@router.callback_query(CartCb.filter(F.action.in_({"inc", "dec"})))
async def cart_change(call: CallbackQuery, callback_data: CartCb, session: AsyncSession) -> None:
    delta = 1 if callback_data.action == "inc" else -1
    result = await repo.change_cart_qty(session, call.from_user.id, callback_data.item_id, delta)
    notes = {
        "no_stock": "Більше немає на складі",
        "missing": "Цієї позиції вже немає в кошику",
        "removed": "Позицію видалено",
    }
    text, markup = await _cart_view(session, call.from_user.id)
    await render(call, text, markup)
    await call.answer(notes.get(result, ""))


@router.callback_query(CartCb.filter(F.action == "del"))
async def cart_delete(call: CallbackQuery, callback_data: CartCb, session: AsyncSession) -> None:
    await repo.remove_cart_item(session, call.from_user.id, callback_data.item_id)
    text, markup = await _cart_view(session, call.from_user.id)
    await render(call, text, markup)
    await call.answer("Видалено")


@router.callback_query(CartCb.filter(F.action == "clear"))
async def cart_clear(call: CallbackQuery, session: AsyncSession) -> None:
    await repo.clear_cart(session, call.from_user.id)
    await render(call, cart_text([]))
    await call.answer("Кошик очищено")
