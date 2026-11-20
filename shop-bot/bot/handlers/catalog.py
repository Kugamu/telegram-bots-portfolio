"""Каталог: категорії → товари (з пагінацією) → картка товару; пошук."""
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..keyboards import user as kb
from ..keyboards.callbacks import CatalogCb
from ..states import SearchSG
from ..utils.render import render
from ..utils.text import product_card

router = Router(name="catalog")


@router.message(F.text == kb.BTN_CATALOG)
async def catalog_entry(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    cats = await repo.list_categories(session)
    if not cats:
        await message.answer("Каталог поки порожній — скоро тут з'являться товари 🙌")
        return
    await message.answer("<b>🛍 Каталог</b>\nОберіть категорію:", reply_markup=kb.categories_kb(cats))


@router.callback_query(CatalogCb.filter(F.action == "root"))
async def catalog_root(call: CallbackQuery, session: AsyncSession) -> None:
    cats = await repo.list_categories(session)
    await render(call, "<b>🛍 Каталог</b>\nОберіть категорію:", kb.categories_kb(cats))
    await call.answer()


@router.callback_query(CatalogCb.filter(F.action == "cat"))
async def show_category(call: CallbackQuery, callback_data: CatalogCb, session: AsyncSession) -> None:
    cat = await repo.get_category(session, callback_data.cat_id)
    if cat is None:
        await call.answer("Категорію не знайдено — можливо, її видалили.", show_alert=True)
        return
    products, pages = await repo.list_products(session, cat.id, callback_data.page)
    if not products:
        await call.answer("У цій категорії поки немає товарів", show_alert=True)
        return
    await render(call, f"<b>{escape(cat.name)}</b>\nОберіть товар:", kb.products_kb(products, cat.id, callback_data.page, pages))
    await call.answer()


@router.callback_query(CatalogCb.filter(F.action == "prod"))
async def show_product(call: CallbackQuery, callback_data: CatalogCb, session: AsyncSession) -> None:
    p = await repo.get_product(session, callback_data.product_id)
    if p is None or not p.is_active:
        await call.answer("Цей товар більше недоступний 😔", show_alert=True)
        return
    from_search = callback_data.page < 0
    await render(call, product_card(p), kb.product_kb(p, callback_data.page, back_to_search=from_search), photo=p.photo)
    await call.answer()


@router.callback_query(CatalogCb.filter(F.action == "add"))
async def add_to_cart(call: CallbackQuery, callback_data: CatalogCb, session: AsyncSession) -> None:
    p = await repo.get_product(session, callback_data.product_id)
    if p is None or not p.is_active:
        await call.answer("Цей товар більше недоступний 😔", show_alert=True)
        return
    # користувач міг не натискати /start (наприклад, після очищення БД) — реєструємо
    u = call.from_user
    await repo.upsert_user(session, u.id, u.username, u.full_name)
    ok, qty = await repo.add_to_cart(session, u.id, p)
    if ok:
        await call.answer(f"✅ Додано! У кошику: {qty} шт.")
    else:
        await call.answer(f"Більше немає на складі (доступно {p.stock} шт.)", show_alert=True)


# ---------- пошук ----------
@router.message(F.text == kb.BTN_SEARCH)
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchSG.query)
    await message.answer("🔎 Введіть назву або частину опису товару (наприклад: <i>ефіопія</i>, <i>матча</i>):",
                         reply_markup=kb.cancel_kb())


@router.message(SearchSG.query, F.text)
async def search_query(message: Message, session: AsyncSession, state: FSMContext) -> None:
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Запит закороткий — введіть хоча б 2 символи.")
        return
    results = await repo.search_products(session, query)
    await state.clear()
    if not results:
        await message.answer(f"За запитом «{escape(query)}» нічого не знайдено 🤷", reply_markup=kb.main_menu())
        return
    await message.answer("Знайшов для вас:", reply_markup=kb.main_menu())
    await message.answer(f"🔎 Результати за «{escape(query)}»:", reply_markup=kb.search_results_kb(results))


@router.message(SearchSG.query)
async def search_not_text(message: Message) -> None:
    await message.answer("Надішліть, будь ласка, текстовий запит або натисніть «✖️ Скасувати».")
