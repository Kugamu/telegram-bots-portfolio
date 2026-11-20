"""Клавіатури адмін-панелі."""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..db.models import STATUS_LABELS, Category, Order, OrderStatus, Product
from ..utils.text import money
from .callbacks import AdminCb


def _back(kb: InlineKeyboardBuilder, cb: AdminCb, text: str = "⬅️ Назад") -> None:
    kb.button(text=text, callback_data=cb)


def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 Товари", callback_data=AdminCb(section="prods", action="cats"))
    kb.button(text="🗂 Категорії", callback_data=AdminCb(section="cats"))
    kb.button(text="🧾 Замовлення", callback_data=AdminCb(section="orders"))
    kb.button(text="📊 Статистика", callback_data=AdminCb(section="stats"))
    kb.button(text="📣 Розсилка", callback_data=AdminCb(section="mail"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()


# ---------- категорії ----------
def categories_admin_kb(cats: list[Category]):
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=c.name, callback_data=AdminCb(section="cats", action="view", id=c.id))
    kb.button(text="➕ Нова категорія", callback_data=AdminCb(section="cats", action="new"))
    _back(kb, AdminCb(section="menu"))
    kb.adjust(1)
    return kb.as_markup()


def category_admin_kb(cat_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Перейменувати", callback_data=AdminCb(section="cats", action="rename", id=cat_id))
    kb.button(text="🗑 Видалити", callback_data=AdminCb(section="cats", action="delete", id=cat_id))
    _back(kb, AdminCb(section="cats"))
    kb.adjust(1)
    return kb.as_markup()


# ---------- товари ----------
def prod_categories_kb(cats: list[Category]):
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=c.name, callback_data=AdminCb(section="prods", action="list", id=c.id))
    _back(kb, AdminCb(section="menu"))
    kb.adjust(1)
    return kb.as_markup()


def products_admin_kb(products: list[Product], cat_id: int, page: int, pages: int):
    kb = InlineKeyboardBuilder()
    for p in products:
        flags = ("" if p.is_active else "🙈 ") + ("" if p.stock > 0 else "⛔️ ")
        kb.button(text=f"{flags}{p.name} — {money(p.price)} ({p.stock} шт.)",
                  callback_data=AdminCb(section="prods", action="view", id=p.id, page=page))
    nav = 0
    if page > 0:
        kb.button(text="◀️", callback_data=AdminCb(section="prods", action="list", id=cat_id, page=page - 1)); nav += 1
    if page < pages - 1:
        kb.button(text="▶️", callback_data=AdminCb(section="prods", action="list", id=cat_id, page=page + 1)); nav += 1
    kb.button(text="➕ Додати товар", callback_data=AdminCb(section="prods", action="new", id=cat_id))
    _back(kb, AdminCb(section="prods", action="cats"))
    kb.adjust(*([1] * len(products)), *([nav] if nav else []), 1, 1)
    return kb.as_markup()


EDITABLE_FIELDS = {
    "name": "✏️ Назва",
    "price": "💰 Ціна",
    "description": "📝 Опис",
    "stock": "📦 Залишок",
    "photo": "🖼 Фото",
}


def product_admin_kb(p: Product, page: int):
    kb = InlineKeyboardBuilder()
    for field, title in EDITABLE_FIELDS.items():
        kb.button(text=title, callback_data=AdminCb(section="prods", action="edit", id=p.id, page=page, value=field))
    kb.button(text="🙈 Приховати" if p.is_active else "👁 Показати",
              callback_data=AdminCb(section="prods", action="toggle", id=p.id, page=page))
    kb.button(text="🗑 Видалити", callback_data=AdminCb(section="prods", action="delete", id=p.id, page=page))
    _back(kb, AdminCb(section="prods", action="list", id=p.category_id, page=page))
    kb.adjust(2, 2, 1, 2, 1)
    return kb.as_markup()


def confirm_delete_kb(section: str, obj_id: int, page: int = 0):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Так, видалити", callback_data=AdminCb(section=section, action="delete_yes", id=obj_id, page=page))
    kb.button(text="Ні", callback_data=AdminCb(section=section, action="view", id=obj_id, page=page))
    kb.adjust(2)
    return kb.as_markup()


# ---------- замовлення ----------
def order_filters_kb(counts: dict):
    kb = InlineKeyboardBuilder()
    for status, label in STATUS_LABELS.items():
        kb.button(text=f"{label} ({counts.get(status, 0)})",
                  callback_data=AdminCb(section="orders", action="list", value=status.value))
    _back(kb, AdminCb(section="menu"))
    kb.adjust(1)
    return kb.as_markup()


def orders_list_kb(orders: list[Order], status: OrderStatus):
    kb = InlineKeyboardBuilder()
    for o in orders:
        kb.button(text=f"№{o.id} · {money(o.total)} · {o.customer_name[:20]}",
                  callback_data=AdminCb(section="orders", action="view", id=o.id))
    _back(kb, AdminCb(section="orders"))
    kb.adjust(1)
    return kb.as_markup()


def order_admin_kb(order: Order, with_back: bool = True):
    kb = InlineKeyboardBuilder()
    for status, label in STATUS_LABELS.items():
        if status is not order.status:
            kb.button(text=f"→ {label}", callback_data=AdminCb(section="orders", action="set", id=order.id, value=status.value))
    if order.receipt_file_id:
        kb.button(text="🧾 Показати чек", callback_data=AdminCb(section="orders", action="receipt", id=order.id))
    if with_back:
        _back(kb, AdminCb(section="orders", action="list", value=order.status.value), "⬅️ До списку")
    kb.adjust(2)
    return kb.as_markup()


# ---------- розсилка ----------
def broadcast_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Надіслати всім", callback_data=AdminCb(section="mail", action="send"))
    kb.button(text="✖️ Скасувати", callback_data=AdminCb(section="mail", action="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu_kb():
    kb = InlineKeyboardBuilder()
    _back(kb, AdminCb(section="menu"), "⬅️ В адмін-меню")
    return kb.as_markup()
