"""Inline-клавиатуры для бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from packages.domain.categories import CATEGORY_KEYS, label_for


def review_card_keyboard(receipt_id: int, *, can_save: bool = True, locale: str = "ru") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_save:
        rows.append([InlineKeyboardButton(text="✅ Сохранить", callback_data=f"rcpt:save:{receipt_id}")])
    rows.append([
        InlineKeyboardButton(text="✏️ Сумма", callback_data=f"rcpt:edit_amount:{receipt_id}"),
        InlineKeyboardButton(text="✏️ Категория", callback_data=f"rcpt:edit_category:{receipt_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="✏️ Вендор", callback_data=f"rcpt:edit_vendor:{receipt_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"rcpt:cancel:{receipt_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_picker_keyboard(receipt_id: int, locale: str = "ru") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    # 2 кнопки в ряд
    chunk: list[InlineKeyboardButton] = []
    for key in CATEGORY_KEYS:
        chunk.append(InlineKeyboardButton(
            text=label_for(key, locale).capitalize(),
            callback_data=f"rcpt:set_category:{receipt_id}:{key}",
        ))
        if len(chunk) == 2:
            rows.append(chunk)
            chunk = []
    if chunk:
        rows.append(chunk)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def project_switch_keyboard(projects: list[tuple[int, str, bool]]) -> InlineKeyboardMarkup:
    """projects = [(id, name, is_active), ...]"""
    rows = []
    for pid, name, active in projects:
        marker = "🟢 " if active else ""
        rows.append([InlineKeyboardButton(text=f"{marker}{name}", callback_data=f"proj:switch:{pid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_download_keyboard(project_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📥 Скачать таблицу", callback_data=f"rep:xlsx:{project_id}"),
    ]])


def new_project_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Создать", callback_data="np:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="np:cancel"),
    ]])
