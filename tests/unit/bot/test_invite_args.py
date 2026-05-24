from __future__ import annotations

from apps.bot.handlers.invites import _parse_args


def test_empty_default():
    assert _parse_args("") == (False, None)


def test_just_number_means_project_member_with_quota():
    assert _parse_args("3") == (False, 3)


def test_quota_keyword():
    assert _parse_args("quota 5") == (True, 5)


def test_quota_keyword_russian():
    assert _parse_args("квота 10") == (True, 10)


def test_garbage_falls_back():
    assert _parse_args("blah") == (False, None)


def test_negative_clamped_to_zero():
    # int("-5") parses → max(0, -5) = 0 (т.е. немедленный quota exceeded)
    assert _parse_args("-5") == (False, 0)
