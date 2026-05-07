"""Verify work_hardening_ratio against textbook example values."""

from __future__ import annotations

import pytest

from process_calc import InputOutOfRangeError, calculate


def test_textbook_example_n_30pct():
    """Construct a textbook-shaped example: H₀=2.0 GPa, H=2.6 GPa →
    N = (2.6-2.0)/2.0 × 100 = 30%."""
    result = calculate("work_hardening_ratio", H_gpa=2.6, H0_gpa=2.0)
    payload = result["result"]
    assert payload["delta_gpa"] == 0.6
    assert payload["N_percent"] == 30.0
    assert result["unit"] == "%"
    assert result["verified"] is True
    assert result["implementation_status"] == "verified"


def test_typical_lathe_n_120():
    """Per Ch4 表 4-41 普通车 N=120-150%. Constructed: H₀=2.0, H=4.4 → N=120%."""
    result = calculate("work_hardening_ratio", H_gpa=4.4, H0_gpa=2.0)
    assert result["result"]["N_percent"] == 120.0


def test_zero_or_negative_h0_raises():
    with pytest.raises(InputOutOfRangeError):
        calculate("work_hardening_ratio", H_gpa=2.6, H0_gpa=0.0)
    with pytest.raises(InputOutOfRangeError):
        calculate("work_hardening_ratio", H_gpa=2.6, H0_gpa=-1.0)


def test_zero_or_negative_h_raises():
    with pytest.raises(InputOutOfRangeError):
        calculate("work_hardening_ratio", H_gpa=0.0, H0_gpa=2.0)
    with pytest.raises(InputOutOfRangeError):
        calculate("work_hardening_ratio", H_gpa=-2.0, H0_gpa=2.0)


def test_steps_describe_derivation():
    result = calculate("work_hardening_ratio", H_gpa=2.6, H0_gpa=2.0)
    text = " ".join(result["steps"])
    assert "ΔH" in text or "H - H₀" in text
    assert "N" in text
    assert "100%" in text
