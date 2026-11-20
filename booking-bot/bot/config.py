"""Конфігурація бота: читається з .env / змінних оточення."""
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    admin_ids: Annotated[list[int], NoDecode] = []
    database_url: str = "sqlite+aiosqlite:///data/booking.db"

    business_name: str = "Barber Club"
    business_address: str = "м. Київ, вул. Хрещатик, 1"
    business_phone: str = "+380 67 000 00 00"
    timezone: str = "Europe/Kyiv"

    slot_step_min: int = 30          # крок сітки слотів
    booking_days_ahead: int = 30     # на скільки днів уперед можна записатися
    min_lead_min: int = 30           # мінімум хвилин від «зараз» до запису
    remind_hours: int = 2            # за скільки годин нагадати
    cancel_min_hours: int = 2        # пізніше цього скасувати можна лише по телефону

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

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
