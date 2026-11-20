"""Точка входу: python -m bot"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from .config import get_settings
from .db.engine import create_tables, make_engine, make_sessionmaker
from .handlers import admin, chat, fallback, lead, start
from .middlewares import DbSessionMiddleware
from .services.ai import AIConsultant


async def set_commands(bot: Bot, admin_ids: list[int]) -> None:
    user_cmds = [BotCommand(command="start", description="Почати спочатку"),
                 BotCommand(command="reset", description="Новий діалог"),
                 BotCommand(command="cancel", description="Скасувати дію")]
    await bot.set_my_commands(user_cmds)
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(user_cmds + [BotCommand(command="admin", description="Адмін-панель")],
                                      scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            logging.warning("Адмін %s ще не відкривав бота — команди не встановлено", admin_id)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, stream=sys.stdout,
                        format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not settings.anthropic_api_key:
        logging.warning("ANTHROPIC_API_KEY не задано — AI-відповіді не працюватимуть, але заявки збиратимуться")

    engine = make_engine(settings.database_url)
    await create_tables(engine)
    sessionmaker = make_sessionmaker(engine)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    dp = Dispatcher(storage=MemoryStorage())
    dp["ai"] = AIConsultant()  # доступний у хендлерах як аргумент `ai`
    dp.update.middleware(DbSessionMiddleware(sessionmaker))
    # chat — після FSM-роутерів: туди потрапляє лише вільний текст поза сценаріями
    dp.include_routers(start.router, lead.router, admin.router, chat.router, fallback.router)

    try:
        await set_commands(bot, settings.admin_ids)
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Бот запущено. Модель: %s", settings.claude_model)
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        logging.critical("Telegram відхилив BOT_TOKEN — перевірте токен у файлі .env")
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено")
