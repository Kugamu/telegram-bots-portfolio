"""Адмін-панель. Усі під-роутери захищені фільтром IsAdmin."""
from aiogram import Router

from ...filters import IsAdmin
from . import bookings, broadcast, masters, menu, services

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
router.include_routers(menu.router, bookings.router, services.router, masters.router, broadcast.router)
