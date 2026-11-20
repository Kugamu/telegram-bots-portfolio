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
from .db.seed import seed_demo
from .handlers import admin, cart, catalog, checkout, fallback, start
from .middlewares import DbSessionMiddleware


async def set_commands(bot: Bot, admin_ids: list[int]) -> None:
    user_cmds = [BotCommand(command="start", description="Головне меню"),
                 BotCommand(command="cancel", description="Скасувати поточну дію")]
    await bot.set_my_commands(user_cmds)
    for admin_id in admin_ids:  # адмінам додатково показуємо /admin
        try:
            await bot.set_my_commands(user_cmds + [BotCommand(command="admin", description="Адмін-панель")],
                                      scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            logging.warning("Адмін %s ще не відкривав бота — команди не встановлено", admin_id)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
        stream=sys.stdout,
    )

    engine = make_engine(settings.database_url)
    await create_tables(engine)
    sessionmaker = make_sessionmaker(engine)
    if settings.seed_demo_data:
        await seed_demo(sessionmaker)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    # MemoryStorage достатньо для демо; у продакшені — RedisStorage, щоб стани переживали рестарт
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware(sessionmaker))
    # Порядок важливий: start (кнопки меню з будь-якого стану) → функціонал → адмінка → fallback
    dp.include_routers(start.router, catalog.router, cart.router, checkout.router, admin.router, fallback.router)

    try:
        await set_commands(bot, settings.admin_ids)
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Бот запущено. Адміни: %s", settings.admin_ids or "не задано")
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
