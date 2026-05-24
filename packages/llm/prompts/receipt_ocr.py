"""Receipt OCR prompt + structured response model. Used by both MiMo and Gemini."""

from __future__ import annotations

import datetime as _dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Category = Literal[
    "furniture", "decor", "textile", "delivery", "labor",
    "supplies", "photo", "rental", "transport", "other",
]


class OCRItem(BaseModel):
    name: str
    qty: float = 1.0
    price: float | None = None


class OCRResult(BaseModel):
    """Структурированный ответ LLM на промпт распознавания чека.

    NB: Python-поле `purchased_at` имеет alias `"date"` — именно так его шлёт
    LLM в JSON. Прямое имя `date` в Pydantic v2 ломается через PEP 604 (`date | None`)
    из-за конфликта между именем поля и именем типа.
    """

    model_config = ConfigDict(populate_by_name=True)

    amount: float | None = Field(
        None, description="Итоговая сумма (TOTAL/ИТОГО) в денежных единицах"
    )
    currency: Literal["RUB", "USD", "EUR"] = "RUB"
    vendor: str | None = None
    purchased_at: _dt.date | None = Field(None, alias="date")
    category_guess: Category = "other"
    items: list[OCRItem] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)

    def is_reliable(self) -> bool:
        return self.amount is not None and self.confidence >= 0.6


RECEIPT_OCR_PROMPT = """\
Ты помощник для обработки чеков. На вход — фото чека.
Извлеки данные и ответь СТРОГО валидным JSON. Без markdown, без комментариев, без префиксов.

Схема ответа:
{
  "amount": number | null,    // ИТОГО / TOTAL / К ОПЛАТЕ. Не подитог. null если не видно.
  "currency": "RUB" | "USD" | "EUR",
  "vendor": string | null,    // название магазина/поставщика
  "date": "YYYY-MM-DD" | null,
  "category_guess": "furniture" | "decor" | "textile" | "delivery" | "labor"
                  | "supplies" | "photo" | "rental" | "transport" | "other",
  "items": [{"name": string, "qty": number, "price": number}],
  "confidence": number        // 0.0 - 1.0, твоя уверенность в данных
}

Правила:
1. amount = только итоговая сумма к оплате. Игнорируй подитоги и скидки отдельно.
2. Если фото нечитаемое или это не чек — confidence < 0.3, остальное best effort или null.
3. Категория выбирается по вендору + items:
   - furniture: ИКЕА, мебельные магазины, диваны/столы/кровати
   - decor: вазы, картины, статуэтки, свечи
   - textile: шторы, подушки, пледы, постельное
   - delivery: транспортные услуги, грузчики, доставка магазина
   - labor: оплата бригаде, монтаж, уборка
   - supplies: краска, инструменты, расходные материалы, хозтовары
   - photo: фотограф, печать, реквизит для съёмки
   - rental: аренда мебели/декора (НЕ покупка)
   - transport: бензин, такси для себя
   - other: всё остальное
4. items опционально. Если не уверен — пустой массив.
5. Никакого текста вне JSON.
"""
