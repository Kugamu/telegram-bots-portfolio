"""/start, головне меню, прайс, контакти, скасування діалогу.
Підключається першим — кнопки меню працюють з будь-якого FSM-стану."""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..keyboards import user as kb
from ..utils.text import service_line

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    u = message.from_user
    await repo.upsert_user(session, u.id, u.username, u.full_name)
    await message.answer(
        f"Привіт, {escape(u.first_name)}! 👋\n\n"
        f"Це бот <b>{escape(get_settings().business_name)}</b>. Тут можна за хвилину записатися "
        "до майстра на зручний час, переглянути або скасувати свій запис.\n\n"
        "Я нагадаю про візит заздалегідь ⏰",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text == kb.BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Дію скасовано.", reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_PRICES)
async def prices(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    services = await repo.list_services(session)
    lines = "\n".join(f"• {escape(service_line(s))}" for s in services) or "Прайс оновлюється 🙂"
    await message.answer(f"💈 <b>Послуги та ціни</b>\n\n{lines}", reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_CONTACTS)
async def contacts(message: Message, state: FSMContext) -> None:
    await state.clear()
    s = get_settings()
    await message.answer(
        f"<b>{escape(s.business_name)}</b>\n\n📍 {escape(s.business_address)}\n📞 {escape(s.business_phone)}\n\n"
        "Команди: /start — меню, /cancel — скасувати дію",
        reply_markup=kb.main_menu(),
    )
