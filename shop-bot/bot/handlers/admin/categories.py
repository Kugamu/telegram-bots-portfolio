"""CRUD категорій."""
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...states import AdminCategorySG
from ...utils.render import render

router = Router(name="admin_categories")


async def _show_list(call: CallbackQuery, session: AsyncSession) -> None:
    cats = await repo.list_categories(session)
    await render(call, "🗂 <b>Категорії</b>", akb.categories_admin_kb(cats))


@router.callback_query(AdminCb.filter((F.section == "cats") & (F.action == "list")))
async def cats_list(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await _show_list(call, session)
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "cats") & (F.action == "view")))
async def cat_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    cat = await repo.get_category(session, callback_data.id)
    if cat is None:
        await call.answer("Категорію вже видалено", show_alert=True)
        return await _show_list(call, session)
    n = await repo.count_products_in_category(session, cat.id)
    await render(call, f"🗂 <b>{escape(cat.name)}</b>\nТоварів: {n}", akb.category_admin_kb(cat.id))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "cats") & (F.action == "new")))
async def cat_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminCategorySG.name)
    await call.message.answer("Введіть назву нової категорії (можна з емодзі, напр. <i>🍫 Шоколад</i>).\n/cancel — скасувати")
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "cats") & (F.action == "rename")))
async def cat_rename(call: CallbackQuery, callback_data: AdminCb, state: FSMContext) -> None:
    await state.set_state(AdminCategorySG.rename)
    await state.update_data(cat_id=callback_data.id)
    await call.message.answer("Введіть нову назву категорії.\n/cancel — скасувати")
    await call.answer()


@router.message(AdminCategorySG.name, F.text)
@router.message(AdminCategorySG.rename, F.text)
async def cat_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 64:
        return await message.answer("Назва має бути від 2 до 64 символів.")
    if await repo.category_name_exists(session, name):
        return await message.answer("Така категорія вже існує. Введіть іншу назву.")
    if await state.get_state() == AdminCategorySG.rename.state:
        cat = await repo.get_category(session, (await state.get_data())["cat_id"])
        if cat is None:
            await state.clear()
            return await message.answer("Категорію вже видалено.")
        cat.name = name
        await session.commit()
        done = f"✅ Категорію перейменовано на «{escape(name)}»"
    else:
        await repo.create_category(session, name)
        done = f"✅ Категорію «{escape(name)}» створено"
    await state.clear()
    cats = await repo.list_categories(session)
    await message.answer(done, reply_markup=akb.categories_admin_kb(cats))


@router.message(AdminCategorySG.name)
@router.message(AdminCategorySG.rename)
async def cat_expect_text(message: Message) -> None:
    await message.answer("Надішліть назву текстом або /cancel.")


@router.callback_query(AdminCb.filter((F.section == "cats") & (F.action == "delete")))
async def cat_delete(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    if await repo.count_products_in_category(session, callback_data.id):
        await call.answer("У категорії є товари. Спочатку видаліть або приховайте їх.", show_alert=True)
        return
    await render(call, "Видалити категорію? Цю дію не можна скасувати.", akb.confirm_delete_kb("cats", callback_data.id))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "cats") & (F.action == "delete_yes")))
async def cat_delete_yes(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    cat = await repo.get_category(session, callback_data.id)
    if cat and not await repo.count_products_in_category(session, cat.id):
        await session.delete(cat)
        await session.commit()
        await call.answer("Категорію видалено")
    else:
        await call.answer("Не вдалося видалити", show_alert=True)
    await _show_list(call, session)
