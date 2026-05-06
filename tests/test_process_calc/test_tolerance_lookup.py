"""Sprint C Phase 1 — ISO 286-1 tolerance lookup verification."""

from __future__ import annotations

import pytest

from process_calc import calculate


def test_phi_50_h7_matches_iso_286_1():
    """φ50 H7: IT7 grade for 30-50mm range = 25 μm; H fundamental deviation = 0.
    Upper = +25 μm, Lower = 0."""
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="H7")
    payload = result["result"]
    assert payload["upper_deviation_um"] == 25
    assert payload["lower_deviation_um"] == 0
    assert payload["tolerance_um"] == 25
    assert result["verified"] is True
    assert result["implementation_status"] == "verified"
    assert result["unit"] == "μm"


def test_phi_25_h7_matches_iso_286_1():
    """φ25 H7: IT7 for 18-30mm = 21 μm; upper = +21, lower = 0."""
    result = calculate("tolerance_lookup_iso", diameter_mm=25.0, fit_class="H7")
    payload = result["result"]
    assert payload["upper_deviation_um"] == 21
    assert payload["lower_deviation_um"] == 0
    assert payload["tolerance_um"] == 21


def test_phi_100_h7_matches_iso_286_1():
    """φ100 H7: IT7 for 80-120mm = 35 μm; upper = +35, lower = 0."""
    result = calculate("tolerance_lookup_iso", diameter_mm=100.0, fit_class="H7")
    payload = result["result"]
    assert payload["upper_deviation_um"] == 35
    assert payload["lower_deviation_um"] == 0


def test_phi_50_h6_shaft_fit():
    """φ50 h6: IT6 for 30-50mm = 16 μm; h fundamental deviation = 0 upper.
    Upper = 0, Lower = -16 μm."""
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="h6")
    payload = result["result"]
    assert payload["upper_deviation_um"] == 0
    assert payload["lower_deviation_um"] == -16
    assert payload["tolerance_um"] == 16


def test_phi_50_g6_shaft_fit():
    """φ50 g6: IT6 for 30-50mm = 16 μm; g fundamental deviation = -9 μm upper.
    Upper = -9, Lower = -25 μm."""
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="g6")
    payload = result["result"]
    assert payload["upper_deviation_um"] == -9
    assert payload["lower_deviation_um"] == -25
    assert payload["tolerance_um"] == 16


def test_phi_50_h8_hole_grade():
    """φ50 H8: IT8 for 30-50mm = 39 μm; H upper = +39, lower = 0."""
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="H8")
    payload = result["result"]
    assert payload["upper_deviation_um"] == 39
    assert payload["lower_deviation_um"] == 0


def test_returns_steps_with_grade_and_letter_decomposition():
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="H7")
    steps = result["steps"]
    text = " ".join(steps)
    assert "IT7" in text or "IT 7" in text
    assert "H" in text
    assert any("30" in step for step in steps)


def test_returns_formula_referencing_iso_286():
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="H7")
    assert "286" in result["formula"]


def test_unsupported_fit_class_raises():
    from process_calc import InputOutOfRangeError

    with pytest.raises(InputOutOfRangeError):
        calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="z9")


def test_dca_003_question_shape_can_be_satisfied():
    """DCA-003 expects: result + steps + formula + warnings present."""
    result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="H7")
    assert result["result"] is not None
    assert result["steps"]
    assert result["formula"]
    assert isinstance(result["warnings"], list)
