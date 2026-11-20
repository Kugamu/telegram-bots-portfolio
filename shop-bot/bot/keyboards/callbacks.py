"""Типізовані callback_data (aiogram CallbackData factory) — без «магічних рядків»."""
from aiogram.filters.callback_data import CallbackData


class CatalogCb(CallbackData, prefix="cat"):
    action: str  # root | cat | prod | add
    cat_id: int = 0
    product_id: int = 0
    page: int = 0


class CartCb(CallbackData, prefix="cart"):
    action: str  # show | inc | dec | del | clear | checkout
    item_id: int = 0


class CheckoutCb(CallbackData, prefix="co"):
    action: str  # pay_card | pay_cod | confirm | cancel


class AdminCb(CallbackData, prefix="adm"):
    """Навігація адмінки. section: menu | cats | prods | orders | stats | mail."""
    section: str
    action: str = "list"
    id: int = 0
    page: int = 0
    value: str = ""
