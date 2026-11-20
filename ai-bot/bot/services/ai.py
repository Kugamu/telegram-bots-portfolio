"""AI-консультант на Claude API.

- Відповідає лише за базою знань компанії (FAQ із файлу), не вигадує ціни й умови.
- Системний промпт із базою знань кешується (prompt caching) — дешевше й швидше на кожному запиті.
- Коли клієнт готовий до замовлення, модель додає маркер, і бот пропонує залишити заявку.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import anthropic

from ..config import get_settings

log = logging.getLogger(__name__)

LEAD_MARKER = "[ЗАЯВКА]"

SYSTEM_TEMPLATE = """Ти — онлайн-консультант компанії «{business}» у Telegram. Твоя задача — коротко й \
доброзичливо відповідати на запитання клієнтів та допомагати їм дійти до заявки.

Правила:
1. Відповідай ЛИШЕ на основі бази знань нижче. Якщо відповіді там немає — чесно скажи, що уточнить \
менеджер, і запропонуй залишити заявку. Ніколи не вигадуй ціни, терміни, гарантії чи контакти.
2. Пиши українською (або мовою клієнта), простими словами, 2–6 речень. Без Markdown-розмітки: \
лише звичайний текст, можна емодзі та списки з «•».
3. Якщо клієнт хоче замовити, просить прорахунок, виїзд замірника, дзвінок менеджера або залишити \
контакти — коротко підтвердь і в самому кінці відповіді додай окремим рядком маркер {marker}. \
В інших випадках маркер не додавай.
4. Не обговорюй теми, не пов'язані з компанією; ввічливо поверни розмову до послуг.
5. Не проси клієнта писати номер телефону в чат — для цього є кнопка «Залишити заявку».

=== БАЗА ЗНАНЬ ===
{knowledge}
=== КІНЕЦЬ БАЗИ ЗНАНЬ ==="""


@dataclass
class AIReply:
    text: str
    wants_lead: bool
    input_tokens: int = 0
    output_tokens: int = 0


class AIUnavailable(Exception):
    """Тимчасова проблема з API — показуємо клієнту дружнє повідомлення."""


class AIConsultant:
    def __init__(self) -> None:
        s = get_settings()
        # без ключа клієнт створюється, але запити повертатимуть зрозумілу помилку
        self.client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None, max_retries=2, timeout=60)
        self.system_prompt = ""
        self.reload_knowledge()

    def reload_knowledge(self) -> int:
        """Перечитує FAQ з файлу (команда «Оновити базу знань» в адмінці). Повертає довжину бази."""
        s = get_settings()
        path = Path(s.knowledge_file)
        knowledge = path.read_text(encoding="utf-8") if path.exists() else "База знань порожня."
        if not path.exists():
            log.warning("Файл бази знань %s не знайдено", path)
        self.system_prompt = SYSTEM_TEMPLATE.format(business=s.business_name, marker=LEAD_MARKER, knowledge=knowledge)
        return len(knowledge)

    async def ask(self, history: list[dict]) -> AIReply:
        s = get_settings()
        if not s.anthropic_api_key:
            log.error("ANTHROPIC_API_KEY не задано в .env — AI-відповіді вимкнено")
            raise AIUnavailable("no api key")
        extra: dict = {}
        if s.claude_fallbacks:
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        try:
            response = await self.client.beta.messages.create(
                model=s.claude_model,
                max_tokens=s.max_tokens,
                # стабільний системний промпт кешується між запитами всіх користувачів
                system=[{"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=history,
                output_config={"effort": s.claude_effort},
                **extra,
            )
        except anthropic.AuthenticationError as e:
            log.error("Невірний ANTHROPIC_API_KEY: %s", e)
            raise AIUnavailable from e
        except anthropic.RateLimitError as e:
            log.warning("Ліміт запитів Claude API: %s", e)
            raise AIUnavailable from e
        except anthropic.APIStatusError as e:
            log.error("Помилка Claude API %s: %s", e.status_code, e.message)
            raise AIUnavailable from e
        except anthropic.APIConnectionError as e:
            log.error("Немає з'єднання з Claude API: %s", e)
            raise AIUnavailable from e

        if response.stop_reason == "refusal":
            return AIReply("Вибачте, з цим питанням я допомогти не можу 🙏 Можу розповісти про наші послуги.", False)

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        wants_lead = LEAD_MARKER in text
        text = text.replace(LEAD_MARKER, "").strip() or "Зрозумів вас! Залиште, будь ласка, заявку — менеджер зв'яжеться з вами."
        usage = response.usage
        return AIReply(text, wants_lead, usage.input_tokens, usage.output_tokens)
