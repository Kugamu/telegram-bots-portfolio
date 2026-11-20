"""Сповіщення адміністраторів і клієнтів."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from ..config import get_settings
from ..db.models import Order
from ..keyboards.admin import order_admin_kb
from ..utils.text import order_text

log = logging.getLogger(__name__)


async def notify_admins_new_order(bot: Bot, order: Order) -> None:
    text = "🔔 <b>Нове замовлення!</b>\n\n" + order_text(order, for_admin=True)
    markup = order_admin_kb(order, with_back=False)
    for admin_id in get_settings().admin_ids:
        try:
            if order.receipt_file_id:
                await bot.send_photo(admin_id, order.receipt_file_id, caption=text[:1024], reply_markup=markup)
            else:
                await bot.send_message(admin_id, text, reply_markup=markup)
        except TelegramAPIError as e:
            # адмін ще не натиснув /start у боті або заблокував його
            log.warning("Не вдалося сповістити адміна %s: %s", admin_id, e)


async def notify_customer_status(bot: Bot, order: Order) -> None:
    try:
        await bot.send_message(
            order.user_id,
            f"📦 Статус вашого замовлення <b>№{order.id}</b> змінено: <b>{order.status.label}</b>",
        )
    except TelegramAPIError as e:
        log.info("Клієнт %s недоступний: %s", order.user_id, e)
