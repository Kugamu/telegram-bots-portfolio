"""Майстри: CRUD, призначення послуг, робочий графік по днях тижня."""
import re
from datetime import time
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...db.models import Master, WorkingHours
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...states import AdminMasterSG
from ...utils.render import render
from ...utils.text import WEEKDAYS_FULL, schedule_text

router = Router(name="admin_masters")

HOURS_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})\s*$")


def _card(m: Master) -> str:
    services = ", ".join(escape(s.name) for s in m.services) or "— не призначено"
    status = "👁 Приймає записи" if m.is_active else "🙈 Прихований"
    return (f"👤 <b>{escape(m.name)}</b>\n{escape(m.description)}\n\n"
            f"<b>Послуги:</b> {services}\n\n<b>Графік:</b>\n{schedule_text(m)}\n\n<i>{status}</i>")


def parse_hours(text: str) -> tuple[time, time] | None:
    m = HOURS_RE.match(text or "")
    if not m:
        return None
    h1, m1, h2, m2 = map(int, m.groups())
    if not (0 <= h1 <= 23 and 0 <= h2 <= 23 and m1 < 60 and m2 < 60):
        return None
    start, end = time(h1, m1), time(h2, m2)
    return (start, end) if start < end else None


async def _get(call: CallbackQuery, session: AsyncSession, master_id: int) -> Master | None:
    m = await repo.get_master(session, master_id)
    if m is None:
        await call.answer("Майстра вже видалено", show_alert=True)
    return m


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "list")))
async def mst_list(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await render(call, "👤 <b>Майстри</b>", akb.masters_admin_kb(await repo.list_masters(session, only_active=False)))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "view")))
async def mst_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if m := await _get(call, session, callback_data.id):
        await render(call, _card(m), akb.master_admin_kb(m))
        await call.answer()


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "toggle")))
async def mst_toggle(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    if m := await _get(call, session, callback_data.id):
        m.is_active = not m.is_active
        await session.commit()
        await render(call, _card(m), akb.master_admin_kb(m))
        await call.answer("Збережено")


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "delete")))
async def mst_delete(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    if await repo.count_bookings(session, master_id=callback_data.id):
        return await call.answer("У майстра є записи в історії — його можна лише приховати.", show_alert=True)
    await render(call, "Видалити майстра назавжди?", akb.confirm_delete_kb("mst", callback_data.id))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "delete_yes")))
async def mst_delete_yes(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, state: FSMContext) -> None:
    m = await repo.get_master(session, callback_data.id)
    if m and not await repo.count_bookings(session, master_id=m.id):
        await session.delete(m)
        await session.commit()
    await mst_list(call, session, state)


# ---------- послуги майстра ----------
@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "services")))
async def mst_services(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    if m := await _get(call, session, callback_data.id):
        services = await repo.list_services(session, only_active=False)
        await render(call, f"💈 Послуги майстра <b>{escape(m.name)}</b> (натисніть, щоб увімкнути/вимкнути):",
                     akb.master_services_kb(m, services))
        await call.answer()


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "svc_toggle")))
async def mst_service_toggle(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    m = await _get(call, session, callback_data.id)
    s = await repo.get_service(session, int(callback_data.value or 0))
    if m is None or s is None:
        return await call.answer("Не знайдено", show_alert=True) if m else None
    if s in m.services:
        m.services.remove(s)
    else:
        m.services.append(s)
    await session.commit()
    await mst_services(call, callback_data, session)


# ---------- графік ----------
@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "schedule")))
async def mst_schedule(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if m := await _get(call, session, callback_data.id):
        await render(call, f"🕒 Графік <b>{escape(m.name)}</b>\nНатисніть на день, щоб змінити години:", akb.master_schedule_kb(m))
        await call.answer()


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "day")))
async def mst_day(call: CallbackQuery, callback_data: AdminCb, state: FSMContext) -> None:
    wd = int(callback_data.value or 0) % 7
    await state.set_state(AdminMasterSG.hours)
    await state.update_data(id=callback_data.id, weekday=wd)
    await call.message.answer(
        f"<b>{WEEKDAYS_FULL[wd]}</b>: введіть години роботи у форматі <code>10:00-19:00</code>\n"
        "або <code>-</code>, якщо це вихідний.\n/cancel — скасувати"
    )
    await call.answer()


@router.message(AdminMasterSG.hours)
async def mst_day_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    m = await repo.get_master(session, data["id"])
    if m is None:
        await state.clear()
        return await message.answer("Майстра вже видалено.")
    text = (message.text or "").strip()
    if text in {"-", "—", "вихідний"}:
        await repo.set_hours(session, m, data["weekday"], None, None)
    elif parsed := parse_hours(text):
        await repo.set_hours(session, m, data["weekday"], *parsed)
    else:
        return await message.answer("Не розпізнав формат 🤔 Приклад: <code>09:30-18:00</code> або <code>-</code>")
    await state.clear()
    await session.refresh(m, ["hours"])
    await message.answer(f"✅ Графік оновлено\n\n{schedule_text(m)}", reply_markup=akb.master_schedule_kb(m))


# ---------- створення / редагування ----------
@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "new")))
async def mst_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminMasterSG.name)
    await call.message.answer("➕ <b>Новий майстер</b>\nВведіть ім'я:\n/cancel — скасувати")
    await call.answer()


@router.message(AdminMasterSG.name)
async def mst_new_name(message: Message, state: FSMContext) -> None:
    if not message.text or not 2 <= len(message.text) <= 64:
        return await message.answer("Ім'я: від 2 до 64 символів.")
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminMasterSG.description)
    await message.answer("Короткий опис (досвід, спеціалізація):")


@router.message(AdminMasterSG.description)
async def mst_new_desc(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.text or len(message.text) > 300:
        return await message.answer("Опис — текстом, до 300 символів.")
    data = await state.get_data()
    # Значення за замовчуванням, щоб майстер одразу був «робочим»: усі послуги, Пн–Пт 10–19
    m = Master(name=data["name"], description=message.text.strip(),
               services=await repo.list_services(session, only_active=False))
    m.hours = [WorkingHours(weekday=d, start=time(10), end=time(19)) for d in range(5)]
    session.add(m)
    await session.commit()
    await state.clear()
    await message.answer("✅ Майстра додано з графіком Пн–Пт 10:00–19:00 і всіма послугами — змініть за потреби.\n\n" + _card(m),
                         reply_markup=akb.master_admin_kb(m))


@router.callback_query(AdminCb.filter((F.section == "mst") & (F.action == "edit")))
async def mst_edit(call: CallbackQuery, callback_data: AdminCb, state: FSMContext) -> None:
    await state.set_state(AdminMasterSG.edit_field)
    await state.update_data(id=callback_data.id, field="name" if callback_data.value == "name" else "description")
    await call.message.answer(("Нове ім'я:" if callback_data.value == "name" else "Новий опис:") + "\n/cancel — скасувати")
    await call.answer()


@router.message(AdminMasterSG.edit_field)
async def mst_edit_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    m = await repo.get_master(session, data["id"])
    if m is None:
        await state.clear()
        return await message.answer("Майстра вже видалено.")
    limit = 64 if data["field"] == "name" else 300
    if not message.text or not 2 <= len(message.text) <= limit:
        return await message.answer(f"Текстом, від 2 до {limit} символів.")
    setattr(m, data["field"], message.text.strip())
    await session.commit()
    await state.clear()
    await message.answer("✅ Збережено\n\n" + _card(m), reply_markup=akb.master_admin_kb(m))
