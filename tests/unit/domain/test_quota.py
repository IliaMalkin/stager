from __future__ import annotations

import pytest

from packages.domain.quota import QuotaExceeded, check_quota, decrement_quota


def test_unlimited_quota_passes():
    check_quota(None)  # должен не упасть


def test_positive_quota_passes():
    check_quota(3)


def test_zero_quota_raises():
    with pytest.raises(QuotaExceeded) as exc:
        check_quota(0)
    assert exc.value.quota == 0


def test_negative_quota_raises():
    with pytest.raises(QuotaExceeded):
        check_quota(-1)


def test_decrement_unlimited_stays_unlimited():
    assert decrement_quota(None) is None


def test_decrement_normal():
    assert decrement_quota(5) == 4


def test_decrement_to_zero():
    assert decrement_quota(1) == 0


def test_decrement_below_zero_clamps():
    assert decrement_quota(0) == 0
