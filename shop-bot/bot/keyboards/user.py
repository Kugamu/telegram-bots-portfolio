"""Клавіатури для покупця."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from ..db.models import CartItem, Category, Product
from ..utils.text import money
from .callbacks import CartCb, CatalogCb, CheckoutCb

BTN_CATALOG = "🛍 Каталог"
BTN_SEARCH = "🔎 Пошук"
BTN_CART = "🛒 Кошик"
BTN_ORDERS = "📦 Мої замовлення"
BTN_ABOUT = "ℹ️ Про магазин"
BTN_CANCEL = "✖️ Скасувати"


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for text in (BTN_CATALOG, BTN_SEARCH, BTN_CART, BTN_ORDERS, BTN_ABOUT):
        kb.button(text=text)
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Оберіть розділ меню")


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Надіслати мій номер", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def categories_kb(categories: list[Category]):
    kb = InlineKeyboardBuilder()
    for c in categories:
        kb.button(text=c.name, callback_data=CatalogCb(action="cat", cat_id=c.id))
    kb.adjust(1)
    return kb.as_markup()


def products_kb(products: list[Product], cat_id: int, page: int, pages: int):
    kb = InlineKeyboardBuilder()
    for p in products:
        mark = "" if p.stock > 0 else " (немає)"
        kb.button(
            text=f"{p.name} — {money(p.price)}{mark}",
            callback_data=CatalogCb(action="prod", cat_id=cat_id, product_id=p.id, page=page),
        )
    kb.adjust(1)
    nav = []
    if page > 0:
        nav.append(("◀️", CatalogCb(action="cat", cat_id=cat_id, page=page - 1)))
    if pages > 1:
        nav.append((f"{page + 1}/{pages}", CatalogCb(action="cat", cat_id=cat_id, page=page)))
    if page < pages - 1:
        nav.append(("▶️", CatalogCb(action="cat", cat_id=cat_id, page=page + 1)))
    for text, cb in nav:
        kb.button(text=text, callback_data=cb)
    kb.button(text="⬅️ До категорій", callback_data=CatalogCb(action="root"))
    kb.adjust(*([1] * len(products)), *([len(nav)] if nav else []), 1)
    return kb.as_markup()


def product_kb(product: Product, page: int, back_to_search: bool = False):
    kb = InlineKeyboardBuilder()
    if product.stock > 0:
        kb.button(
            text="🛒 Додати в кошик",
            callback_data=CatalogCb(action="add", cat_id=product.category_id, product_id=product.id, page=page),
        )
    kb.button(text="🛒 Перейти до кошика", callback_data=CartCb(action="show"))
    if not back_to_search:
        kb.button(text="⬅️ Назад", callback_data=CatalogCb(action="cat", cat_id=product.category_id, page=page))
    kb.adjust(1)
    return kb.as_markup()


def search_results_kb(products: list[Product]):
    kb = InlineKeyboardBuilder()
    for p in products:
        kb.button(
            text=f"{p.name} — {money(p.price)}",
            callback_data=CatalogCb(action="prod", cat_id=p.category_id, product_id=p.id, page=-1),
        )
    kb.adjust(1)
    return kb.as_markup()


def cart_kb(items: list[CartItem]):
    kb = InlineKeyboardBuilder()
    for i in items:
        kb.button(text=f"{i.product.name[:24]} ×{i.quantity}", callback_data=CartCb(action="noop", item_id=i.id))
        kb.button(text="➖", callback_data=CartCb(action="dec", item_id=i.id))
        kb.button(text="➕", callback_data=CartCb(action="inc", item_id=i.id))
        kb.button(text="❌", callback_data=CartCb(action="del", item_id=i.id))
    kb.button(text="✅ Оформити замовлення", callback_data=CartCb(action="checkout"))
    kb.button(text="🗑 Очистити кошик", callback_data=CartCb(action="clear"))
    kb.adjust(*([1, 3] * len(items)), 1, 1)
    return kb.as_markup()


def payment_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Переказ на карту", callback_data=CheckoutCb(action="pay_card"))
    kb.button(text="📦 Накладений платіж", callback_data=CheckoutCb(action="pay_cod"))
    kb.button(text="✖️ Скасувати", callback_data=CheckoutCb(action="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити замовлення", callback_data=CheckoutCb(action="confirm"))
    kb.button(text="✖️ Скасувати", callback_data=CheckoutCb(action="cancel"))
    kb.adjust(1)
    return kb.as_markup()
