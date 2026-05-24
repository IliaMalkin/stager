"""Категории расходов — fixed enum, single source of truth для бота, API и LLM."""

from __future__ import annotations

from typing import Literal

Category = Literal[
    "furniture", "decor", "textile", "delivery", "labor",
    "supplies", "photo", "rental", "transport", "other",
]

CATEGORY_KEYS: tuple[Category, ...] = (
    "furniture", "decor", "textile", "delivery", "labor",
    "supplies", "photo", "rental", "transport", "other",
)

CATEGORY_LABELS: dict[str, dict[Category, str]] = {
    "ru": {
        "furniture": "мебель",
        "decor": "декор",
        "textile": "текстиль",
        "delivery": "доставка",
        "labor": "бригада",
        "supplies": "расходники",
        "photo": "фото",
        "rental": "аренда",
        "transport": "транспорт",
        "other": "прочее",
    },
    "en": {
        "furniture": "furniture",
        "decor": "decor",
        "textile": "textile",
        "delivery": "delivery",
        "labor": "labor",
        "supplies": "supplies",
        "photo": "photo",
        "rental": "rental",
        "transport": "transport",
        "other": "other",
    },
}

# обратный маппинг для парсинга /add: RU-слово → ключ
_REVERSE_RU: dict[str, Category] = {v: k for k, v in CATEGORY_LABELS["ru"].items()}
_REVERSE_EN: dict[str, Category] = {v: k for k, v in CATEGORY_LABELS["en"].items()}


def parse_category(token: str, locale: str = "ru") -> Category | None:
    """Принимает строку (мебель / furniture / FURNITURE) → канонический ключ или None."""
    t = token.strip().lower()
    if t in CATEGORY_KEYS:
        return t  # type: ignore[return-value]
    if t in _REVERSE_RU:
        return _REVERSE_RU[t]
    if t in _REVERSE_EN:
        return _REVERSE_EN[t]
    return None


def label_for(key: Category, locale: str = "ru") -> str:
    return CATEGORY_LABELS.get(locale, CATEGORY_LABELS["ru"])[key]
