"""Minimal i18n: load JSON dicts at import, expose `t(key, locale)`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_BUNDLES: dict[str, dict[str, Any]] = {}
_HERE = Path(__file__).parent


def _load() -> None:
    for f in _HERE.glob("*.json"):
        _BUNDLES[f.stem] = json.loads(f.read_text(encoding="utf-8"))


_load()


def t(key: str, locale: str = "ru", **kwargs: Any) -> str:
    bundle = _BUNDLES.get(locale) or _BUNDLES.get("ru") or {}
    value = bundle
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part, key)
        else:
            return key
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except KeyError:
            return value
    return value if isinstance(value, str) else key
