"""FSM-стани (кінцеві автомати діалогів)."""
from aiogram.fsm.state import State, StatesGroup


class SearchSG(StatesGroup):
    query = State()


class CheckoutSG(StatesGroup):
    name = State()
    phone = State()
    address = State()
    payment = State()
    receipt = State()
    confirm = State()


class AdminCategorySG(StatesGroup):
    name = State()
    rename = State()


class AdminProductSG(StatesGroup):
    # створення нового товару
    name = State()
    description = State()
    price = State()
    stock = State()
    photo = State()
    # редагування одного поля існуючого товару
    edit_field = State()


class BroadcastSG(StatesGroup):
    message = State()
    confirm = State()
