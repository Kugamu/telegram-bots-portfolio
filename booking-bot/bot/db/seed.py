"""Демо-дані барбершопу: послуги, майстри та їхні графіки."""
import logging
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .models import Master, Service, WorkingHours

log = logging.getLogger(__name__)

SERVICES = [
    ("💇‍♂️ Чоловіча стрижка", 45, 450),
    ("🧔 Стрижка + борода", 75, 700),
    ("✂️ Оформлення бороди", 30, 300),
    ("👦 Дитяча стрижка", 30, 350),
    ("🪒 Королівське гоління", 45, 500),
]

# ім'я, опис, індекси послуг, робочі дні (0=Пн), години
MASTERS = [
    ("Олег", "Топ-барбер, 8 років досвіду. Класичні та фейд-стрижки.", [0, 1, 2, 4], [0, 1, 2, 3, 4], (10, 19)),
    ("Андрій", "Майстер бороди й гоління небезпечною бритвою.", [0, 1, 2, 4], [1, 2, 3, 4, 5], (11, 20)),
    ("Марина", "Стрижки для дорослих і дітей, терпляча до найменших клієнтів 🙂", [0, 3], [0, 2, 4, 5, 6], (10, 18)),
]


async def seed_demo(sessionmaker: async_sessionmaker) -> None:
    async with sessionmaker() as session:
        if await session.scalar(select(func.count(Service.id))):
            return
        services = [Service(name=n, duration_min=d, price=p) for n, d, p in SERVICES]
        session.add_all(services)
        for name, desc, svc_idx, days, (h_from, h_to) in MASTERS:
            m = Master(name=name, description=desc, services=[services[i] for i in svc_idx])
            m.hours = [WorkingHours(weekday=d, start=time(h_from), end=time(h_to)) for d in days]
            session.add(m)
        await session.commit()
        log.info("Демо-дані додано: %d послуг, %d майстрів", len(SERVICES), len(MASTERS))
