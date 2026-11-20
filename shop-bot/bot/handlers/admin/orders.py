"""Перегляд замовлень і зміна статусів (з автоматичним сповіщенням клієнта)."""
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...db.models import Order, OrderStatus
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...services.notify import notify_customer_status
from ...utils.render import render
from ...utils.text import order_text

router = Router(name="admin_orders")


@router.callback_query(AdminCb.filter((F.section == "orders") & (F.action == "list") & (F.value == "")))
async def orders_filters(call: CallbackQuery, session: AsyncSession) -> None:
    counts = dict((await session.execute(select(Order.status, func.count(Order.id)).group_by(Order.status))).all())
    await render(call, "🧾 <b>Замовлення</b>\nОберіть статус:", akb.order_filters_kb(counts))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "orders") & (F.action == "list")))
async def orders_list(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    try:
        status = OrderStatus(callback_data.value)
    except ValueError:
        return await call.answer("Невідомий статус", show_alert=True)
    orders = await repo.orders_by_status(session, status)
    text = f"🧾 <b>{status.label}</b>: {len(orders)}" + ("" if orders else "\n\nТут поки порожньо.")
    await render(call, text, akb.orders_list_kb(orders, status))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "orders") & (F.action == "view")))
async def order_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    order = await repo.get_order(session, callback_data.id)
    if order is None:
        return await call.answer("Замовлення не знайдено", show_alert=True)
    await render(call, order_text(order, for_admin=True), akb.order_admin_kb(order))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "orders") & (F.action == "set")))
async def order_set_status(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, bot: Bot) -> None:
    order = await repo.get_order(session, callback_data.id)
    if order is None:
        return await call.answer("Замовлення не знайдено", show_alert=True)
    new_status = OrderStatus(callback_data.value)
    if order.status is new_status:
        return await call.answer("Статус уже встановлено")
    await repo.set_order_status(session, order, new_status)
    await call.answer(f"Статус: {new_status.label}")

    text = order_text(order, for_admin=True)
    msg = call.message
    # Сповіщення про нове замовлення може бути фото з чеком — тоді редагуємо підпис
    if isinstance(msg, Message) and msg.photo:
        try:
            await msg.edit_caption(caption=text[:1024], reply_markup=akb.order_admin_kb(order, with_back=False))
        except TelegramBadRequest:
            pass
    else:
        await render(call, text, akb.order_admin_kb(order))
    await notify_customer_status(bot, order)


@router.callback_query(AdminCb.filter((F.section == "orders") & (F.action == "receipt")))
async def order_receipt(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    order = await repo.get_order(session, callback_data.id)
    if order is None or not order.receipt_file_id:
        return await call.answer("Чек не знайдено", show_alert=True)
    await call.message.answer_photo(order.receipt_file_id, caption=f"🧾 Чек до замовлення №{order.id}")
    await call.answer()
