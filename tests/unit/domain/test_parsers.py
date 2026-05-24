from __future__ import annotations

import pytest

from packages.domain.parsers import AddCommandParseError, parse_add_command


def test_parse_full():
    p = parse_add_command("4850 мебель диван из ИКЕА")
    assert p.amount_minor == 485000
    assert p.category == "furniture"
    assert p.description == "диван из ИКЕА"


def test_parse_decimal_comma():
    p = parse_add_command("4850,50 декор ваза")
    assert p.amount_minor == 485050
    assert p.category == "decor"


def test_parse_amount_only():
    p = parse_add_command("100")
    assert p.amount_minor == 10000
    assert p.category == "other"
    assert p.description is None


def test_parse_no_category_keyword():
    p = parse_add_command("100 такси до объекта")
    assert p.amount_minor == 10000
    assert p.category == "other"
    assert p.description == "такси до объекта"


def test_parse_en_category():
    p = parse_add_command("50 furniture chair")
    assert p.category == "furniture"


def test_parse_invalid_amount():
    with pytest.raises(AddCommandParseError):
        parse_add_command("abc мебель")


def test_parse_empty():
    with pytest.raises(AddCommandParseError):
        parse_add_command("")
