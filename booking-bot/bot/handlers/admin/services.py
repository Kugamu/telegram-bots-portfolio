"""CRUD послуг."""
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...db.models import Service
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...states import AdminServiceSG
from ...utils.render import render
from ...utils.text import duration, money

router = Router(name="admin_services")

PROMPTS = {
    "name": "Введіть назву послуги (можна з емодзі):",
    "duration": "Тривалість у хвилинах (наприклад 45):",
    "price": "Ціна в гривнях (ціле число):",
}


def _card(s: Service) -> str:
    status = "👁 Доступна для запису" if s.is_active else "🙈 Прихована"
    return f"💈 <b>{escape(s.name)}</b>\n⏱ {duration(s.duration_min)}\n💰 {money(s.price)}\n\n<i>{status}</i>"


def _int(text: str, lo: int, hi: int) -> int | None:
    text = (text or "").strip()
    return int(text) if text.isdigit() and lo <= int(text) <= hi else None


@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "list")))
async def svc_list(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await render(call, "💈 <b>Послуги</b>", akb.services_admin_kb(await repo.list_services(session, only_active=False)))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "view")))
async def svc_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    s = await repo.get_service(session, callback_data.id)
    if s is None:
        return await call.answer("Послугу вже видалено", show_alert=True)
    await render(call, _card(s), akb.service_admin_kb(s))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "toggle")))
async def svc_toggle(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    s = await repo.get_service(session, callback_data.id)
    if s is None:
        return await call.answer("Послугу вже видалено", show_alert=True)
    s.is_active = not s.is_active
    await session.commit()
    await render(call, _card(s), akb.service_admin_kb(s))
    await call.answer("Збережено")


@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "delete")))
async def svc_delete(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    if await repo.count_bookings(session, service_id=callback_data.id):
        return await call.answer("На цю послугу є записи в історії — її можна лише приховати.", show_alert=True)
    await render(call, "Видалити послугу назавжди?", akb.confirm_delete_kb("svc", callback_data.id))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "delete_yes")))
async def svc_delete_yes(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, state: FSMContext) -> None:
    s = await repo.get_service(session, callback_data.id)
    if s and not await repo.count_bookings(session, service_id=s.id):
        await session.delete(s)
        await session.commit()
    await svc_list(call, session, state)


# ---------- створення ----------
@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "new")))
async def svc_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminServiceSG.name)
    await call.message.answer("➕ <b>Нова послуга</b>\n" + PROMPTS["name"] + "\n/cancel — скасувати")
    await call.answer()


@router.message(AdminServiceSG.name)
async def svc_new_name(message: Message, state: FSMContext) -> None:
    if not message.text or not 2 <= len(message.text) <= 64:
        return await message.answer("Назва: від 2 до 64 символів.")
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminServiceSG.duration)
    await message.answer(PROMPTS["duration"])


@router.message(AdminServiceSG.duration)
async def svc_new_duration(message: Message, state: FSMContext) -> None:
    value = _int(message.text, 5, 600)
    if value is None:
        return await message.answer("Введіть число від 5 до 600.")
    await state.update_data(duration=value)
    await state.set_state(AdminServiceSG.price)
    await message.answer(PROMPTS["price"])


@router.message(AdminServiceSG.price)
async def svc_new_price(message: Message, session: AsyncSession, state: FSMContext) -> None:
    value = _int(message.text, 0, 1_000_000)
    if value is None:
        return await message.answer("Введіть ціле число.")
    data = await state.get_data()
    s = Service(name=data["name"], duration_min=data["duration"], price=value)
    session.add(s)
    await session.commit()
    await state.clear()
    await message.answer("✅ Послугу створено. Не забудьте призначити її майстрам (👤 Майстри → 💈 Послуги).\n\n" + _card(s),
                         reply_markup=akb.service_admin_kb(s))


# ---------- редагування ----------
@router.callback_query(AdminCb.filter((F.section == "svc") & (F.action == "edit")))
async def svc_edit(call: CallbackQuery, callback_data: AdminCb, state: FSMContext) -> None:
    if callback_data.value not in PROMPTS:
        return await call.answer()
    await state.set_state(AdminServiceSG.edit_field)
    await state.update_data(id=callback_data.id, field=callback_data.value)
    await call.message.answer(PROMPTS[callback_data.value] + "\n/cancel — скасувати")
    await call.answer()


@router.message(AdminServiceSG.edit_field)
async def svc_edit_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    s = await repo.get_service(session, data["id"])
    if s is None:
        await state.clear()
        return await message.answer("Послугу вже видалено.")
    field = data["field"]
    if field == "name":
        if not message.text or not 2 <= len(message.text) <= 64:
            return await message.answer("Назва: від 2 до 64 символів.")
        s.name = message.text.strip()
    elif field == "duration":
        if (v := _int(message.text, 5, 600)) is None:
            return await message.answer("Введіть число від 5 до 600.")
        s.duration_min = v  # вже створені записи зберігають свій час
    else:
        if (v := _int(message.text, 0, 1_000_000)) is None:
            return await message.answer("Введіть ціле число.")
        s.price = v
    await session.commit()
    await state.clear()
    await message.answer("✅ Збережено\n\n" + _card(s), reply_markup=akb.service_admin_kb(s))
