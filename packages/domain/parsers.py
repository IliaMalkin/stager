"""Парсеры пользовательского ввода."""

from __future__ import annotations

from dataclasses import dataclass

from packages.domain.categories import Category, parse_category
from packages.domain.currency import parse_amount_to_minor


class AddCommandParseError(ValueError):
    pass


@dataclass
class ParsedExpense:
    amount_minor: int
    category: Category
    description: str | None


def parse_add_command(args: str) -> ParsedExpense:
    """Парсит хвост `/add 4850 мебель диван из ИКЕА`.

    Правила:
    - первый токен = сумма (обязательно, число)
    - второй токен = категория (опционально; если не валидная — всё после суммы = description, category=other)
    - всё остальное = description
    """
    s = (args or "").strip()
    if not s:
        raise AddCommandParseError(
            "Формат: /add <сумма> [категория] [описание]\nПример: /add 4850 мебель диван"
        )

    parts = s.split(maxsplit=2)
    try:
        amount_minor = parse_amount_to_minor(parts[0])
    except ValueError as exc:
        raise AddCommandParseError(f"Не могу прочитать сумму: {exc}") from exc

    if len(parts) == 1:
        return ParsedExpense(amount_minor=amount_minor, category="other", description=None)

    second = parts[1]
    maybe_cat = parse_category(second)
    if maybe_cat is not None:
        description = parts[2] if len(parts) > 2 else None
        return ParsedExpense(
            amount_minor=amount_minor,
            category=maybe_cat,
            description=description,
        )

    # вторая часть — не категория, значит всё это описание
    rest = " ".join(parts[1:])
    return ParsedExpense(amount_minor=amount_minor, category="other", description=rest)
