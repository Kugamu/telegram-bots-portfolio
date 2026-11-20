"""Останній рубіж: усе, що не обробили інші роутери, + глобальний обробник помилок."""
import logging

from aiogram import Router
from aiogram.types import CallbackQuery, ErrorEvent, Message

from ..keyboards.user import main_menu

router = Router(name="fallback")
log = logging.getLogger(__name__)


@router.callback_query()
async def stale_callback(call: CallbackQuery) -> None:
    # Кнопки зі старих повідомлень, після перезапуску бота або змінених даних
    await call.answer("Ця кнопка застаріла. Відкрийте розділ заново з меню 👇", show_alert=True)


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer("Не зовсім зрозумів 🙂 Скористайтеся кнопками меню нижче.", reply_markup=main_menu())


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    log.exception("Помилка під час обробки апдейту %s", event.update.update_id, exc_info=event.exception)
    # Повідомляємо користувача замість «мовчання», якщо це можливо
    upd = event.update
    try:
        if upd.callback_query:
            await upd.callback_query.answer("Сталася помилка, спробуйте ще раз 🙏", show_alert=True)
        elif upd.message:
            await upd.message.answer("Сталася помилка, спробуйте ще раз або натисніть /start 🙏")
    except Exception:
        pass
    return True
