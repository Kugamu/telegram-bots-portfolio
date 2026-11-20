"""/start, скасування, новий діалог."""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..keyboards import kb

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    u = message.from_user
    await repo.upsert_user(session, u.id, u.username, u.full_name)
    await message.answer(
        f"Вітаю, {escape(u.first_name)}! 👋\n\n"
        f"Я AI-консультант компанії <b>{escape(get_settings().business_name)}</b> — ремонт квартир під ключ.\n"
        "Відповім на запитання про ціни, терміни, етапи робіт і гарантію — цілодобово й без очікування.\n\n"
        "Просто напишіть своє запитання 👇 або оберіть варіант на кнопках.",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text == kb.BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Скасовано. Можете продовжувати ставити запитання 🙂", reply_markup=kb.main_menu())


@router.message(Command("reset"))
@router.message(F.text == kb.BTN_RESET)
async def cmd_reset(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await repo.clear_history(session, message.from_user.id)
    await message.answer("🔄 Починаємо розмову з чистого аркуша. Чим можу допомогти?", reply_markup=kb.main_menu())
