"""CRUD товарів: список по категоріях, створення (покроковий FSM), редагування полів, приховування, видалення."""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...db.models import Product
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...states import AdminProductSG
from ...utils.render import render
from ...utils.text import product_card

router = Router(name="admin_products")

PROMPTS = {
    "name": "Введіть назву товару:",
    "description": "Введіть опис товару:",
    "price": "Введіть ціну в гривнях (ціле число, напр. 450):",
    "stock": "Введіть кількість на складі (ціле число):",
    "photo": "Надішліть фото товару (або /skip, щоб залишити без фото):",
}


def _parse_int(text: str, max_value: int = 10_000_000) -> int | None:
    text = text.replace(" ", "")
    return int(text) if text.isdigit() and int(text) <= max_value else None


async def _show_product(call: CallbackQuery, p: Product, page: int) -> None:
    status = "👁 Показується" if p.is_active else "🙈 Прихований"
    await render(call, f"{product_card(p)}\n\n<i>{status} · ID {p.id}</i>", akb.product_admin_kb(p, page), photo=p.photo)


# ---------- навігація ----------
@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "cats")))
async def prods_categories(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    cats = await repo.list_categories(session)
    await render(call, "📦 <b>Товари</b>\nОберіть категорію:", akb.prod_categories_kb(cats))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "list")))
async def prods_list(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    cat = await repo.get_category(session, callback_data.id)
    if cat is None:
        return await call.answer("Категорію не знайдено", show_alert=True)
    products, pages = await repo.list_products(session, cat.id, callback_data.page, only_active=False)
    text = f"📦 <b>{escape(cat.name)}</b>\n🙈 — прихований, ⛔️ — немає в наявності"
    await render(call, text, akb.products_admin_kb(products, cat.id, callback_data.page, pages))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "view")))
async def prod_view(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    p = await repo.get_product(session, callback_data.id)
    if p is None:
        return await call.answer("Товар уже видалено", show_alert=True)
    await _show_product(call, p, callback_data.page)
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "toggle")))
async def prod_toggle(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    p = await repo.get_product(session, callback_data.id)
    if p is None:
        return await call.answer("Товар уже видалено", show_alert=True)
    p.is_active = not p.is_active
    await session.commit()
    await call.answer("Товар показується в каталозі" if p.is_active else "Товар приховано")
    await _show_product(call, p, callback_data.page)


@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "delete")))
async def prod_delete(call: CallbackQuery, callback_data: AdminCb) -> None:
    await render(call, "Видалити товар назавжди?\n<i>Порада: якщо товар може повернутися — краще приховати його.</i>",
                 akb.confirm_delete_kb("prods", callback_data.id, callback_data.page))
    await call.answer()


@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "delete_yes")))
async def prod_delete_yes(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession) -> None:
    p = await repo.get_product(session, callback_data.id)
    if p is None:
        return await call.answer("Товар уже видалено", show_alert=True)
    cat_id = p.category_id
    await session.delete(p)
    await session.commit()
    products, pages = await repo.list_products(session, cat_id, callback_data.page, only_active=False)
    await render(call, "✅ Товар видалено", akb.products_admin_kb(products, cat_id, callback_data.page, pages))
    await call.answer()


# ---------- створення товару ----------
@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "new")))
async def prod_new(call: CallbackQuery, callback_data: AdminCb, state: FSMContext) -> None:
    await state.set_state(AdminProductSG.name)
    await state.update_data(cat_id=callback_data.id)
    await call.message.answer("➕ <b>Новий товар</b> (крок 1/5)\n" + PROMPTS["name"] + "\n/cancel — скасувати")
    await call.answer()


@router.message(AdminProductSG.name, F.text)
async def prod_new_name(message: Message, state: FSMContext) -> None:
    if not 2 <= len(message.text) <= 128:
        return await message.answer("Назва: від 2 до 128 символів.")
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminProductSG.description)
    await message.answer("Крок 2/5. " + PROMPTS["description"])


@router.message(AdminProductSG.description, F.text)
async def prod_new_desc(message: Message, state: FSMContext) -> None:
    if len(message.text) > 800:
        return await message.answer("Опис задовгий (макс. 800 символів — обмеження підпису до фото).")
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminProductSG.price)
    await message.answer("Крок 3/5. " + PROMPTS["price"])


@router.message(AdminProductSG.price, F.text)
async def prod_new_price(message: Message, state: FSMContext) -> None:
    price = _parse_int(message.text)
    if not price:
        return await message.answer("Ціна має бути додатним цілим числом. Спробуйте ще раз:")
    await state.update_data(price=price)
    await state.set_state(AdminProductSG.stock)
    await message.answer("Крок 4/5. " + PROMPTS["stock"])


@router.message(AdminProductSG.stock, F.text)
async def prod_new_stock(message: Message, state: FSMContext) -> None:
    stock = _parse_int(message.text, 1_000_000)
    if stock is None:
        return await message.answer("Кількість — ціле число ≥ 0. Спробуйте ще раз:")
    await state.update_data(stock=stock)
    await state.set_state(AdminProductSG.photo)
    await message.answer("Крок 5/5. " + PROMPTS["photo"])


@router.message(AdminProductSG.photo, F.photo)
@router.message(AdminProductSG.photo, Command("skip"))
async def prod_new_photo(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    p = Product(
        category_id=data["cat_id"],
        name=data["name"],
        description=data["description"],
        price=data["price"],
        stock=data["stock"],
        photo=message.photo[-1].file_id if message.photo else None,
    )
    session.add(p)
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Товар «{escape(p.name)}» додано (ID {p.id}).",
                         reply_markup=akb.product_admin_kb(p, 0))


@router.message(AdminProductSG.photo)
async def prod_new_photo_wrong(message: Message) -> None:
    await message.answer("Надішліть саме фото (не файл) або /skip.")


# ---------- редагування поля ----------
@router.callback_query(AdminCb.filter((F.section == "prods") & (F.action == "edit")))
async def prod_edit(call: CallbackQuery, callback_data: AdminCb, state: FSMContext) -> None:
    if callback_data.value not in akb.EDITABLE_FIELDS:
        return await call.answer("Невідоме поле", show_alert=True)
    await state.set_state(AdminProductSG.edit_field)
    await state.update_data(product_id=callback_data.id, field=callback_data.value, page=callback_data.page)
    await call.message.answer(PROMPTS[callback_data.value] + "\n/cancel — скасувати")
    await call.answer()


@router.message(AdminProductSG.edit_field)
async def prod_edit_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["field"]
    p = await repo.get_product(session, data["product_id"])
    if p is None:
        await state.clear()
        return await message.answer("Товар уже видалено.")

    if field == "photo":
        if message.photo:
            p.photo = message.photo[-1].file_id
        elif message.text == "/skip":
            p.photo = None
        else:
            return await message.answer("Надішліть фото або /skip, щоб прибрати фото.")
    elif not message.text:
        return await message.answer("Очікую текст.")
    elif field in ("price", "stock"):
        value = _parse_int(message.text)
        if value is None or (field == "price" and value == 0):
            return await message.answer("Потрібне ціле число. Спробуйте ще раз:")
        setattr(p, field, value)
    else:
        limit = 128 if field == "name" else 800
        if not 1 <= len(message.text) <= limit:
            return await message.answer(f"Максимум {limit} символів.")
        setattr(p, field, message.text.strip())

    await session.commit()
    await state.clear()
    await message.answer("✅ Збережено:\n\n" + product_card(p), reply_markup=akb.product_admin_kb(p, data["page"]))
