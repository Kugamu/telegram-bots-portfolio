"""Типізовані callback_data.

Вибір послуги/майстра/дати передається прямо в callback_data, тому навігація
«назад» працює навіть після перезапуску бота (не залежить від FSM-сховища).
"""
from aiogram.filters.callback_data import CallbackData


class BookCb(CallbackData, prefix="b"):
    action: str  # services | svc | mst | cal | day | slot | ign
    sid: int = 0   # service id
    mid: int = 0   # master id
    ymd: str = ""  # YYYYMMDD (для cal — перший день місяця)
    hm: str = ""   # HHMM


class MyCb(CallbackData, prefix="my"):
    action: str  # cancel | cancel_yes | keep | confirm | finish
    id: int = 0


class AdminCb(CallbackData, prefix="adm"):
    section: str  # menu | bk | svc | mst | mail | stats
    action: str = "list"
    id: int = 0
    value: str = ""
