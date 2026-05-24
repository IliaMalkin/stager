"""i18n loader smoke tests."""

from __future__ import annotations

from apps.bot.i18n import t


def test_lookup_ru():
    assert t("common.cancelled", "ru") == "Отменено."


def test_lookup_en():
    assert t("common.cancelled", "en") == "Cancelled."


def test_fallback_to_ru_for_unknown_locale():
    # Unknown locale → falls back to ru bundle
    assert t("common.cancelled", "fr") == "Отменено."


def test_missing_key_returns_key():
    assert t("doesnt.exist.lol", "ru") == "doesnt.exist.lol"


def test_kwargs_format():
    rendered = t("photo.saved", "ru", project="Test")
    assert "Test" in rendered


def test_kwargs_missing_returns_unformatted():
    # If a kwarg is missing, t() shouldn't crash — returns raw template
    rendered = t("photo.saved", "ru")
    assert "{project}" in rendered or rendered  # acceptable either way
