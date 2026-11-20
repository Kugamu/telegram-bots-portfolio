"""Адмін-панель. Усі під-роутери захищені фільтром IsAdmin."""
from aiogram import Router

from ...filters import IsAdmin
from . import broadcast, categories, menu, orders, products

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
router.include_routers(menu.router, categories.router, products.router, orders.router, broadcast.router)
