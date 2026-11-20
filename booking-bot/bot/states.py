"""FSM-стани."""
from aiogram.fsm.state import State, StatesGroup


class BookingSG(StatesGroup):
    name = State()
    phone = State()
    confirm = State()


class AdminServiceSG(StatesGroup):
    name = State()
    duration = State()
    price = State()
    edit_field = State()


class AdminMasterSG(StatesGroup):
    name = State()
    description = State()
    edit_field = State()
    hours = State()


class BroadcastSG(StatesGroup):
    message = State()
    confirm = State()
