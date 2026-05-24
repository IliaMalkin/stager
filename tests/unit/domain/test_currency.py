from __future__ import annotations

import pytest

from packages.domain.currency import format_amount, parse_amount_to_minor


@pytest.mark.parametrize("raw,expected", [
    ("100", 10000),
    ("100.50", 10050),
    ("100,50", 10050),
    ("4 850.50", 485050),
    ("4 850,50", 485050),
    ("0", 0),
    ("0.01", 1),
    # Реальный кейс: мама ввела сумму с пробелами и валютой
    ("1 000 000 руб.", 100000000),
    ("1000000 руб.", 100000000),
    ("4850.50 ₽", 485050),
    ("$4,850.50", 485050),
    ("4.850,50", 485050),   # европейский формат: точка — тысячи, запятая — копейки
    ("1 234 567,89", 123456789),
    ("100$", 10000),
    ("  100  ", 10000),
])
def test_parse_amount(raw, expected):
    assert parse_amount_to_minor(raw) == expected


def test_parse_invalid():
    with pytest.raises(ValueError):
        parse_amount_to_minor("abc")
    with pytest.raises(ValueError):
        parse_amount_to_minor("")
    with pytest.raises(ValueError):
        parse_amount_to_minor("-100")
    with pytest.raises(ValueError):
        parse_amount_to_minor(".")


def test_format_amount_rub():
    assert format_amount(485050, "RUB") == "4 850.50 ₽"


def test_format_amount_small():
    assert format_amount(5, "RUB") == "0.05 ₽"


def test_format_amount_usd():
    assert format_amount(10000, "USD") == "100.00 $"
