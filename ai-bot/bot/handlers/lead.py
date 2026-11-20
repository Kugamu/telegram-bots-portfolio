"""Збір заявки (FSM): ім'я → телефон → опис запиту. Заявка + контекст розмови з AI летять адміну."""
import logging
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..keyboards import kb
from ..states import LeadSG

router = Router(name="lead")
log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{10,18}$")


def normalize_phone(raw: str) -> str | None:
    if not PHONE_RE.match(raw.strip()):
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    return "+" + digits if 11 <= len(digits) <= 15 else None


async def _start(message: Message, state: FSMContext, first_name: str) -> None:
    await state.set_state(LeadSG.name)
    await message.answer("📝 <b>Заявка на прорахунок</b> (крок 1/3)\n\nЯк до вас звертатися?",
                         reply_markup=kb.cancel_kb(first_name[:60]))


@router.message(F.text == kb.BTN_LEAD)
async def lead_from_menu(message: Message, state: FSMContext) -> None:
    await _start(message, state, message.from_user.first_name)


@router.callback_query(kb.LeadCb.filter(F.action == "start"))
async def lead_from_ai(call: CallbackQuery, state: FSMContext) -> None:
    await _start(call.message, state, call.from_user.first_name)
    await call.answer()


@router.message(LeadSG.name, F.text)
async def lead_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 60:
        return await message.answer("Ім'я має містити від 2 до 60 символів.")
    await state.update_data(name=name)
    await state.set_state(LeadSG.phone)
    await message.answer("📞 Крок 2/3. Номер телефону для зв'язку — кнопкою або вручну:", reply_markup=kb.phone_kb())


@router.message(LeadSG.phone, F.contact)
@router.message(LeadSG.phone, F.text)
async def lead_phone(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw if raw.startswith(("+", "0")) else "+" + raw)
    if phone is None:
        return await message.answer("Номер виглядає некоректно 🤔 Приклад: <code>+380671234567</code>")
    await state.update_data(phone=phone)
    await state.set_state(LeadSG.request)
    await message.answer(
        "🏠 Крок 3/3. Коротко опишіть задачу: тип об'єкта, площа, що потрібно зробити, бажані терміни.\n"
        "<i>Наприклад: «2-кімнатна у новобудові, 65 м², ремонт під ключ, хочемо до весни»</i>",
        reply_markup=kb.cancel_kb(),
    )


@router.message(LeadSG.request, F.text)
async def lead_request(message: Message, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    text = message.text.strip()
    if len(text) < 5:
        return await message.answer("Опишіть, будь ласка, трохи детальніше 🙏")
    data = await state.get_data()
    await state.clear()
    u = message.from_user
    await repo.upsert_user(session, u.id, u.username, u.full_name)
    lead = await repo.create_lead(session, user_id=u.id, name=data["name"], phone=data["phone"], request=text[:2000])
    log.info("Lead #%s from %s", lead.id, u.id)
    await message.answer(
        f"✅ Дякуємо, {escape(lead.name)}! Заявку №{lead.id} прийнято.\n"
        "Менеджер зателефонує вам протягом робочого дня. А поки можете ставити мені будь-які запитання 🙂",
        reply_markup=kb.main_menu(),
    )

    # контекст розмови допомагає менеджеру підготуватися до дзвінка
    history = await repo.get_history(session, u.id, 6)
    dialog = "\n".join(
        f"{'👤' if m['role'] == 'user' else '🤖'} {escape(m['content'][:300])}" for m in history
    )
    admin_text = (
        f"🔥 <b>Нова заявка №{lead.id}</b>\n\n"
        f"👤 {escape(lead.name)}\n📞 {lead.phone}\n"
        f"🆔 <a href=\"tg://user?id={u.id}\">{escape(u.full_name)}</a>" + (f" @{u.username}" if u.username else "") +
        f"\n\n📝 {escape(lead.request)}" + (f"\n\n<b>Останні повідомлення з AI:</b>\n{dialog}" if dialog else "")
    )
    for admin_id in get_settings().admin_ids:
        try:
            await bot.send_message(admin_id, admin_text[:4096], reply_markup=kb.lead_admin_kb(lead, with_back=False))
        except Exception as e:
            log.warning("Не вдалося сповістити адміна %s: %s", admin_id, e)


@router.message(LeadSG.name)
@router.message(LeadSG.phone)
@router.message(LeadSG.request)
async def lead_expect_text(message: Message) -> None:
    await message.answer("Очікую текстову відповідь 🙂 Або натисніть «✖️ Скасувати».")
