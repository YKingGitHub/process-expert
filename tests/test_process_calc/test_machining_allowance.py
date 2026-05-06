"""Sprint C Phase 1 — finish-to-grind allowance verified against textbook
p.108 缸套 (cylinder liner) example."""

from __future__ import annotations

import pytest

from process_calc import InputOutOfRangeError, calculate


def test_p108_cylinder_liner_inner_finish_to_grind():
    """Textbook p.108: inner φ279.2±0.05 (精车) → φ280.0 (磨).
    diameter_allowance = |280.0 - 279.2| = 0.8
    single_side = 0.4."""
    result = calculate(
        "finish_to_grind_allowance",
        predecessor_diameter_mm=279.2,
        successor_diameter_mm=280.0,
        surface="inner",
    )
    payload = result["result"]
    assert payload["surface"] == "inner"
    assert payload["diameter_allowance_mm"] == 0.8
    assert payload["single_side_allowance_mm"] == 0.4
    assert result["verified"] is True
    assert result["warnings"] == []


def test_p108_cylinder_liner_outer_finish_to_grind():
    """Textbook p.108: outer φ300.8±0.05 (精车) → φ300.0 (磨).
    diameter_allowance = |300.0 - 300.8| = 0.8
    single_side = 0.4."""
    result = calculate(
        "finish_to_grind_allowance",
        predecessor_diameter_mm=300.8,
        successor_diameter_mm=300.0,
        surface="outer",
    )
    payload = result["result"]
    assert payload["surface"] == "outer"
    assert payload["diameter_allowance_mm"] == 0.8
    assert payload["single_side_allowance_mm"] == 0.4
    assert result["warnings"] == []


def test_inverted_direction_raises_warning_but_still_returns():
    """An outer surface with successor > predecessor is unusual; we still
    compute |diff| but emit a direction-inconsistent warning."""
    result = calculate(
        "finish_to_grind_allowance",
        predecessor_diameter_mm=300.0,
        successor_diameter_mm=300.8,
        surface="outer",
    )
    payload = result["result"]
    assert payload["diameter_allowance_mm"] == 0.8
    assert payload["single_side_allowance_mm"] == 0.4
    assert any(w["code"] == "direction_inconsistent_with_surface" for w in result["warnings"])


def test_invalid_surface_raises():
    with pytest.raises(InputOutOfRangeError):
        calculate(
            "finish_to_grind_allowance",
            predecessor_diameter_mm=279.2,
            successor_diameter_mm=280.0,
            surface="lateral",
        )


def test_negative_diameter_raises():
    with pytest.raises(InputOutOfRangeError):
        calculate(
            "finish_to_grind_allowance",
            predecessor_diameter_mm=-279.2,
            successor_diameter_mm=280.0,
            surface="inner",
        )


def test_returned_steps_describe_derivation():
    result = calculate(
        "finish_to_grind_allowance",
        predecessor_diameter_mm=279.2,
        successor_diameter_mm=280.0,
        surface="inner",
    )
    text = " ".join(result["steps"])
    assert "diameter_allowance" in text
    assert "single_side" in text
