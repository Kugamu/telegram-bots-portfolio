"""Універсальний показ «екрану» з callback-кнопки.

Telegram не дозволяє перетворити текстове повідомлення на фото через edit,
а повідомлення старші 48 год не можна ні редагувати, ні видаляти.
Ця функція ховає всі ці нюанси: редагує, коли можна, інакше — надсилає нове.
"""
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

log = logging.getLogger(__name__)


async def render(
    call: CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
    photo: str | None = None,
) -> None:
    msg = call.message
    bot = call.bot
    chat_id = call.from_user.id

    # Текстовий екран і поточне повідомлення теж текстове — просто редагуємо
    if not photo and isinstance(msg, Message) and msg.text is not None:
        try:
            await msg.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
            log.debug("edit_text failed, sending new message: %s", e)

    # Інакше — видаляємо старе (якщо можна) і надсилаємо нове
    if isinstance(msg, Message):
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass

    if photo:
        try:
            await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
            return
        except TelegramBadRequest as e:  # битий URL / file_id — покажемо без фото
            log.warning("Не вдалося надіслати фото %s: %s", photo, e)
    await bot.send_message(chat_id, text, reply_markup=markup)
