"""Inline-клавиатуры формирования. Не требуют БД."""

from __future__ import annotations

from apps.bot.keyboards import (
    category_picker_keyboard,
    new_project_confirm_keyboard,
    project_switch_keyboard,
    report_download_keyboard,
    review_card_keyboard,
)


def test_review_card_with_save():
    kb = review_card_keyboard(42, can_save=True)
    buttons = [b for row in kb.inline_keyboard for b in row]
    save = [b for b in buttons if b.callback_data == "rcpt:save:42"]
    assert len(save) == 1


def test_review_card_no_save_when_low_confidence():
    kb = review_card_keyboard(42, can_save=False)
    buttons = [b for row in kb.inline_keyboard for b in row]
    save = [b for b in buttons if b.callback_data == "rcpt:save:42"]
    assert save == []
    # Cancel и edit_* всегда есть
    assert any(b.callback_data == "rcpt:cancel:42" for b in buttons)
    assert any(b.callback_data == "rcpt:edit_amount:42" for b in buttons)


def test_category_picker_has_all_10():
    kb = category_picker_keyboard(42)
    buttons = [b for row in kb.inline_keyboard for b in row]
    cb_data = [b.callback_data for b in buttons]
    # 10 categories
    assert sum(1 for d in cb_data if d and d.startswith("rcpt:set_category:42:")) == 10


def test_project_switch_marks_active():
    kb = project_switch_keyboard([(1, "A", True), (2, "B", False)])
    buttons = [b for row in kb.inline_keyboard for b in row]
    a = next(b for b in buttons if b.callback_data == "proj:switch:1")
    b_btn = next(b for b in buttons if b.callback_data == "proj:switch:2")
    assert a.text.startswith("🟢")
    assert not b_btn.text.startswith("🟢")


def test_report_download():
    kb = report_download_keyboard(99)
    assert kb.inline_keyboard[0][0].callback_data == "rep:xlsx:99"


def test_new_project_confirm_keyboard():
    kb = new_project_confirm_keyboard()
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert any(b.callback_data == "np:confirm" for b in buttons)
    assert any(b.callback_data == "np:cancel" for b in buttons)
