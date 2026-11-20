"""FSM-стани."""
from aiogram.fsm.state import State, StatesGroup


class LeadSG(StatesGroup):
    name = State()
    phone = State()
    request = State()
