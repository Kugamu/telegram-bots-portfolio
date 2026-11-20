"""Діалог з AI-консультантом: будь-який текст поза FSM-сценаріями йде в Claude."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..keyboards import kb
from ..services.ai import AIConsultant, AIUnavailable

router = Router(name="chat")
log = logging.getLogger(__name__)

MAX_QUESTION_LEN = 2000


@router.message(StateFilter(None), F.text)
async def ask_ai(message: Message, session: AsyncSession, bot: Bot, ai: AIConsultant) -> None:
    s = get_settings()
    u = message.from_user
    question = message.text.strip()
    if question.startswith("/"):
        await message.answer("Невідома команда. Просто напишіть запитання 🙂", reply_markup=kb.main_menu())
        return
    if len(question) > MAX_QUESTION_LEN:
        await message.answer(f"Повідомлення задовге — скоротіть, будь ласка, до {MAX_QUESTION_LEN} символів.")
        return

    await repo.upsert_user(session, u.id, u.username, u.full_name)
    if await repo.requests_last_hour(session, u.id) >= s.rate_limit_per_hour:
        await message.answer("Ви поставили дуже багато запитань за останню годину 🙏 "
                             "Залиште заявку — менеджер відповість особисто.", reply_markup=kb.lead_offer_kb())
        return

    await repo.add_message(session, u.id, "user", question)
    history = await repo.get_history(session, u.id, s.history_limit)

    # «друкує…» поки модель думає
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        try:
            reply = await ai.ask(history)
        except AIUnavailable:
            await message.answer(
                "😔 Вибачте, зараз я тимчасово не можу відповісти. Залиште заявку — і менеджер зв'яжеться з вами.",
                reply_markup=kb.lead_offer_kb(),
            )
            return

    await repo.add_message(session, u.id, "assistant", reply.text, reply.input_tokens, reply.output_tokens)
    # parse_mode=None: текст від моделі не повинен ламати HTML-розмітку Telegram
    await message.answer(reply.text, parse_mode=None,
                         reply_markup=kb.lead_offer_kb() if reply.wants_lead else None)
