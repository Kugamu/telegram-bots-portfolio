"""Сповіщення адміністраторів."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from ..config import get_settings

log = logging.getLogger(__name__)


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in get_settings().admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError as e:
            log.warning("Не вдалося сповістити адміна %s: %s", admin_id, e)
