"""Фонові задачі APScheduler.

Замість окремої задачі на кожен запис (яка загубиться після рестарту) раз на хвилину
перевіряємо БД: це надійно переживає перезапуски й деплої.
"""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import get_settings
from ..db import repo
from ..keyboards.user import reminder_kb
from ..utils.text import booking_text
from .slots import now_local

log = logging.getLogger(__name__)


async def send_reminders(bot: Bot, sessionmaker: async_sessionmaker) -> None:
    s = get_settings()
    async with sessionmaker() as session:
        for b in await repo.due_reminders(session, now_local(), s.remind_hours):
            try:
                await bot.send_message(
                    b.user_id,
                    f"⏰ <b>Нагадування!</b> Чекаємо на вас сьогодні о {b.start_at:%H:%M}\n\n{booking_text(b)}\n\n"
                    f"📍 {s.business_address}",
                    reply_markup=reminder_kb(b.id),
                )
                log.info("Reminder sent for booking #%s", b.id)
            except TelegramForbiddenError:
                await repo.mark_blocked(session, b.user_id)
            except TelegramAPIError as e:
                log.warning("Reminder for #%s failed: %s", b.id, e)
            b.reminded = True  # навіть при помилці — щоб не спамити повторними спробами
        await session.commit()
        closed = await repo.close_finished(session, now_local())
        if closed:
            log.info("Автоматично завершено записів: %s", closed)


def setup_scheduler(bot: Bot, sessionmaker: async_sessionmaker) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=get_settings().tz)
    scheduler.add_job(send_reminders, "interval", minutes=1, args=[bot, sessionmaker],
                      id="reminders", max_instances=1, coalesce=True)
    return scheduler
