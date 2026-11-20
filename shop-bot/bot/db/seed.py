"""Демо-дані: кав'ярня-магазин, щоб бота можна було одразу показати замовнику."""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .models import Category, Product

log = logging.getLogger(__name__)


def _img(text: str, bg: str = "6F4E37") -> str:
    # Плейсхолдер-картинки за URL; в адмінці їх легко замінити на реальні фото.
    return f"https://placehold.co/800x600/{bg}/FFFFFF/png?text={text.replace(' ', '+')}"


DEMO = {
    "☕ Кава в зернах": [
        ("Ефіопія Іргачеф 250 г", "Арабіка 100%. Ноти бергамоту, жасмину та лимона. Світле обсмаження.", 420, 15, _img("Ethiopia")),
        ("Колумбія Супремо 250 г", "Збалансована, з нотами карамелі та горіха. Середнє обсмаження.", 360, 20, _img("Colombia")),
        ("Бразилія Сантос 1 кг", "Шоколадні ноти, ідеальна для еспресо та капучино.", 1150, 8, _img("Brazil")),
        ("Еспресо-бленд 500 г", "Купаж 70/30 арабіка/робуста, щільна крема.", 590, 0, _img("Espresso Blend")),
    ],
    "🍵 Чай": [
        ("Матча церемоніальна 50 г", "Японська матча преміум-класу для чайної церемонії.", 690, 10, _img("Matcha", "4C7A34")),
        ("Ерл Грей 100 г", "Чорний цейлонський чай з олією бергамоту.", 210, 25, _img("Earl Grey", "3E2C23")),
        ("Молочний улун 100 г", "Ніжний вершковий смак, можна заварювати до 5 разів.", 320, 12, _img("Milk Oolong", "8A9A5B")),
    ],
    "🫖 Аксесуари": [
        ("Пуровер V60 керамічний", "Воронка для заварювання фільтр-кави, 1–4 чашки.", 780, 6, _img("V60", "2F4F4F")),
        ("Ручна кавомолка Timemore C3", "Сталеві жорна, 36 ступенів помелу.", 2900, 3, _img("Grinder", "2F4F4F")),
        ("Фільтри паперові 100 шт", "Для пуровера V60 розміру 02.", 190, 40, _img("Filters", "2F4F4F")),
    ],
}


async def seed_demo(sessionmaker: async_sessionmaker) -> None:
    async with sessionmaker() as session:
        if await session.scalar(select(func.count(Category.id))):
            return  # дані вже є — нічого не робимо
        for cat_name, products in DEMO.items():
            cat = Category(name=cat_name)
            session.add(cat)
            for name, desc, price, stock, photo in products:
                session.add(Product(category=cat, name=name, description=desc, price=price, stock=stock, photo=photo))
        await session.commit()
        log.info("Демо-дані додано: %d категорій", len(DEMO))
