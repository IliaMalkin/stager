"""Денежные хелперы. Всё внутри хранится в minor units (копейки)."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CURRENCY_SYMBOL = {"RUB": "₽", "USD": "$", "EUR": "€"}
_NON_BREAKING_SPACE = " "


def parse_amount_to_minor(text: str) -> int:
    """Парсит человеческий ввод суммы → копейки.

    Принимает форматы, типичные для реальных пользователей:
        "100"               → 10000
        "100.50"            → 10050
        "100,50"            → 10050
        "4 850.50"          → 485050
        "1 000 000"         → 100000000
        "1 000 000 руб."    → 100000000   ← главный кейс: пробелы + суффикс
        "4850.50 ₽"         → 485050
        "$4,850.50"         → 485050      (US: запятая = тысячи, точка = копейки)
        "4.850,50"          → 485050      (RU/EU: точка = тысячи, запятая = копейки)

    Эвристика:
    1. Срезаем всё нечисловое (валюта, "руб.", скобки и т.д.)
    2. Последний разделитель (. или ,), за которым ≤ 2 цифры — это decimal
    3. Все остальные . и , — group separators, выкидываем

    Raises ValueError если не парсится.
    """
    if text is None:
        raise ValueError("empty amount")
    s = str(text).strip()
    if not s:
        raise ValueError("empty amount")

    is_negative = s.startswith("-")

    # Выкидываем всё кроме цифр, точек и запятых
    cleaned = re.sub(r"[^\d.,]", "", s)
    if not cleaned:
        raise ValueError(f"cannot parse amount: {text!r}")

    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    last_sep_pos = max(last_dot, last_comma)

    if last_sep_pos >= 0:
        tail_len = len(cleaned) - last_sep_pos - 1
        if 1 <= tail_len <= 2:
            integer_part = cleaned[:last_sep_pos].replace(".", "").replace(",", "")
            decimal_part = cleaned[last_sep_pos + 1:]
            normalized = (integer_part or "0") + "." + decimal_part
        else:
            normalized = cleaned.replace(".", "").replace(",", "")
    else:
        normalized = cleaned

    if not normalized or normalized == ".":
        raise ValueError(f"cannot parse amount: {text!r}")

    try:
        d = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"cannot parse amount: {text!r}") from exc

    if is_negative:
        d = -d
    if d < 0:
        raise ValueError("negative amount not supported")

    minor = (d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)


def format_amount(minor: int, currency: str = "RUB") -> str:
    """485050 RUB → '4 850.50 ₽'."""
    sign = "-" if minor < 0 else ""
    minor_abs = abs(minor)
    units = minor_abs // 100
    cents = minor_abs % 100
    units_str = f"{units:,}".replace(",", _NON_BREAKING_SPACE)
    symbol = _CURRENCY_SYMBOL.get(currency, currency)
    return f"{sign}{units_str}.{cents:02d}{_NON_BREAKING_SPACE}{symbol}"
