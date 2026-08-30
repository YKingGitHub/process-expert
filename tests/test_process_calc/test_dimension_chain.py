"""Sprint C Phase 1 — dimension-chain extreme-method tests + textbook examples."""

from __future__ import annotations

import pytest

from process_calc import InputOutOfRangeError, calculate


# Simple textbook example from §3.2: A=30 +0/-0.05 (increasing),
# B=5 +0.05/0 (decreasing). Closed loop = A - B = 25; closed_es = 0 - 0 = 0;
# closed_ei = -0.05 - 0.05 = -0.10; closed_tolerance = 0.10.
SIMPLE_TEXTBOOK_COMPONENTS = [
    {"name": "A", "basic_dim": 30.0, "es": 0.0, "ei": -0.05, "role": "increasing"},
    {"name": "B", "basic_dim": 5.0, "es": 0.05, "ei": 0.0, "role": "decreasing"},
]


def test_closed_loop_basic_size_simple_textbook_example():
    result = calculate("closed_loop_basic_size", components=SIMPLE_TEXTBOOK_COMPONENTS)
    assert result["result"]["closed_loop_basic_dim"] == 25.0
    assert result["result"]["increasing_sum"] == 30.0
    assert result["result"]["decreasing_sum"] == 5.0
    assert result["verified"] is True


def test_extreme_tolerance_simple_textbook_example():
    result = calculate("extreme_tolerance", components=SIMPLE_TEXTBOOK_COMPONENTS)
    payload = result["result"]
    assert payload["closed_loop_basic_dim"] == 25.0
    assert payload["closed_loop_es"] == 0.0
    assert payload["closed_loop_ei"] == -0.1
    assert payload["closed_loop_tolerance"] == 0.1
    assert payload["max_dimension"] == 25.0
    assert payload["min_dimension"] == 24.9


def test_closed_loop_three_component_example():
    """Three-component chain: A=50+0.05/-0.05 inc, B=10+0/-0.02 dec, C=10+0/-0.02 dec.
    closed_basic = 50 - 10 - 10 = 30
    closed_es = 0.05 - (-0.02) - (-0.02) = 0.09
    closed_ei = -0.05 - 0 - 0 = -0.05
    closed_tolerance = 0.09 - (-0.05) = 0.14"""
    components = [
        {"name": "A", "basic_dim": 50.0, "es": 0.05, "ei": -0.05, "role": "increasing"},
        {"name": "B", "basic_dim": 10.0, "es": 0.0, "ei": -0.02, "role": "decreasing"},
        {"name": "C", "basic_dim": 10.0, "es": 0.0, "ei": -0.02, "role": "decreasing"},
    ]
    basic = calculate("closed_loop_basic_size", components=components)
    tol = calculate("extreme_tolerance", components=components)
    assert basic["result"]["closed_loop_basic_dim"] == 30.0
    assert tol["result"]["closed_loop_es"] == 0.09
    assert tol["result"]["closed_loop_ei"] == -0.05
    assert abs(tol["result"]["closed_loop_tolerance"] - 0.14) < 1e-9


def test_process_dimension_reverse_shaft_textbook_p91():
    """Textbook p.91 spirit: reverse-compute upstream dimensions on a shaft.
    final=50, allowances=[0.5, 1.5, 2.0] (latest-to-earliest passes).
    shaft direction: prev = current + allowance.
    Expected: [50.5, 52.0, 54.0], blank=54.0, total=4.0."""
    result = calculate(
        "process_dimension_reverse",
        final_dimension_mm=50.0,
        allowances_mm=[0.5, 1.5, 2.0],
        direction="shaft",
    )
    payload = result["result"]
    assert payload["process_dimensions_mm"] == [50.5, 52.0, 54.0]
    assert payload["blank_dimension_mm"] == 54.0
    assert payload["total_allowance_mm"] == 4.0
    assert payload["step_count"] == 3
    assert result["verified"] is True


def test_process_dimension_reverse_hole_direction():
    """Hole direction reverses sign: prev = current - allowance.
    final=50, allowances=[0.5, 1.5] → upstream [49.5, 48.0]."""
    result = calculate(
        "process_dimension_reverse",
        final_dimension_mm=50.0,
        allowances_mm=[0.5, 1.5],
        direction="hole",
    )
    payload = result["result"]
    assert payload["process_dimensions_mm"] == [49.5, 48.0]
    assert payload["blank_dimension_mm"] == 48.0


def test_invalid_direction_raises():
    with pytest.raises(InputOutOfRangeError):
        calculate(
            "process_dimension_reverse",
            final_dimension_mm=50.0,
            allowances_mm=[0.5],
            direction="rotational",
        )


def test_negative_allowance_raises():
    with pytest.raises(InputOutOfRangeError):
        calculate(
            "process_dimension_reverse",
            final_dimension_mm=50.0,
            allowances_mm=[0.5, -1.0],
            direction="shaft",
        )


def test_invalid_role_raises():
    bad = [
        {"name": "A", "basic_dim": 30.0, "role": "rotating"},
        {"name": "B", "basic_dim": 5.0, "role": "decreasing"},
    ]
    with pytest.raises(InputOutOfRangeError):
        calculate("closed_loop_basic_size", components=bad)


def test_extreme_tolerance_requires_deviations():
    bad = [
        {"name": "A", "basic_dim": 30.0, "role": "increasing"},
    ]
    with pytest.raises(InputOutOfRangeError):
        calculate("extreme_tolerance", components=bad)


def test_extreme_tolerance_rejects_inverted_deviations():
    """A component with es < ei (upper less than lower) is malformed."""
    bad = [
        {"name": "A", "basic_dim": 30.0, "es": -0.1, "ei": 0.05, "role": "increasing"},
    ]
    with pytest.raises(InputOutOfRangeError):
        calculate("extreme_tolerance", components=bad)


def test_returned_steps_describe_derivation():
    result = calculate("extreme_tolerance", components=SIMPLE_TEXTBOOK_COMPONENTS)
    text = " ".join(result["steps"])
    assert "closed_es" in text
    assert "closed_ei" in text
    assert "closed_tolerance" in text
