"""Конфігурація бота: читається з .env / змінних оточення."""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    # Telegram ID адміністраторів через кому: 123,456
    admin_ids: Annotated[list[int], NoDecode] = []
    database_url: str = "sqlite+aiosqlite:///data/shop.db"

    shop_name: str = "Brew & Bean"
    # Реквізити для оплати на карту (показуються клієнту при оформленні)
    payment_details: str = "Монобанк 5375 0000 0000 0000, ФОП Іваненко І.І."
    # Наповнити БД демо-товарами при першому запуску
    seed_demo_data: bool = True
    log_level: str = "INFO"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, int):
            return [v]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
