"""Створення async-рушія БД і фабрики сесій."""
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from .models import Base


def make_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite"):
        # для SQLite створюємо папку під файл БД, якщо її ще немає
        db_path = url.split("///", 1)[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(url, echo=False, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    # Для демо достатньо create_all; у продакшені — міграції Alembic.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
