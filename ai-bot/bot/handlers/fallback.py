"""Застарілі кнопки, нетекстові повідомлення та глобальний обробник помилок."""
import logging

from aiogram import Router
from aiogram.types import CallbackQuery, ErrorEvent, Message

from ..keyboards.kb import main_menu

router = Router(name="fallback")
log = logging.getLogger(__name__)


@router.callback_query()
async def stale_callback(call: CallbackQuery) -> None:
    await call.answer("Ця кнопка вже неактуальна 🙂", show_alert=True)


@router.message()
async def non_text(message: Message) -> None:
    await message.answer("Поки що я розумію лише текстові повідомлення ✍️ Напишіть, будь ласка, запитання.",
                         reply_markup=main_menu())


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    log.exception("Помилка під час обробки апдейту %s", event.update.update_id, exc_info=event.exception)
    upd = event.update
    try:
        if upd.callback_query:
            await upd.callback_query.answer("Сталася помилка, спробуйте ще раз 🙏", show_alert=True)
        elif upd.message:
            await upd.message.answer("Сталася помилка, спробуйте ще раз або натисніть /start 🙏")
    except Exception:
        pass
    return True
