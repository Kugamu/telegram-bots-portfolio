"""Конфігурація бота: читається з .env / змінних оточення."""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    admin_ids: Annotated[list[int], NoDecode] = []
    database_url: str = "sqlite+aiosqlite:///data/ai.db"

    # --- Claude API ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"
    # low — швидко й економно для чату; medium/high — глибші відповіді, дорожче
    claude_effort: str = "low"
    max_tokens: int = 1024
    # Автоматичний повтор на резервній моделі, якщо основна відхилить запит (server-side fallback)
    claude_fallbacks: bool = True

    business_name: str = "БудКомфорт"
    knowledge_file: str = "knowledge/faq.md"
    history_limit: int = 12          # скільки останніх повідомлень діалогу передавати моделі
    rate_limit_per_hour: int = 30    # захист бюджету: максимум запитів до AI на користувача за годину

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
