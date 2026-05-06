"""Sprint C Phase 1 — dispatcher + return-shape contract tests."""

from __future__ import annotations

import pytest

from process_calc import (
    METHOD_REGISTRY,
    CalculationError,
    InputOutOfRangeError,
    MissingParameterError,
    UnknownMethodError,
    calculate,
)


PHASE1_METHOD_IDS = {
    "tolerance_lookup_iso",
    "closed_loop_basic_size",
    "extreme_tolerance",
    "process_dimension_reverse",
    "finish_to_grind_allowance",
}


REQUIRED_RETURN_FIELDS = {
    "method_id",
    "result",
    "unit",
    "steps",
    "formula",
    "warnings",
    "verified",
    "implementation_status",
}


def test_method_registry_contains_phase1_methods():
    assert PHASE1_METHOD_IDS.issubset(set(METHOD_REGISTRY))


def test_unknown_method_id_raises():
    with pytest.raises(UnknownMethodError):
        calculate("not_a_real_method", x=1)


def test_calculate_returns_uniform_shape_for_each_phase1_method():
    """Run a smoke call against every Phase 1 method and assert the returned
    dict has the contract fields. Per-method correctness is asserted
    elsewhere; this test only pins the public shape."""
    smoke_inputs = {
        "tolerance_lookup_iso": {"diameter_mm": 50.0, "fit_class": "H7"},
        "closed_loop_basic_size": {
            "components": [
                {"name": "A", "basic_dim": 30.0, "es": 0.0, "ei": -0.05, "role": "increasing"},
                {"name": "B", "basic_dim": 5.0, "es": 0.05, "ei": 0.0, "role": "decreasing"},
            ]
        },
        "extreme_tolerance": {
            "components": [
                {"name": "A", "basic_dim": 30.0, "es": 0.0, "ei": -0.05, "role": "increasing"},
                {"name": "B", "basic_dim": 5.0, "es": 0.05, "ei": 0.0, "role": "decreasing"},
            ]
        },
        "process_dimension_reverse": {
            "final_dimension_mm": 50.0,
            "allowances_mm": [0.5, 1.5, 2.0],
            "direction": "shaft",
        },
        "finish_to_grind_allowance": {
            "predecessor_diameter_mm": 279.2,
            "successor_diameter_mm": 280.0,
            "surface": "inner",
        },
    }
    for method_id in PHASE1_METHOD_IDS:
        params = smoke_inputs[method_id]
        result = calculate(method_id, **params)
        for field in REQUIRED_RETURN_FIELDS:
            assert field in result, f"{method_id} missing return field {field}"
        assert result["method_id"] == method_id
        assert isinstance(result["steps"], list)
        assert isinstance(result["warnings"], list)
        assert isinstance(result["verified"], bool)
        assert result["implementation_status"] in {"verified", "implemented", "prototype"}


def test_missing_required_parameter_raises_specific_error():
    with pytest.raises(MissingParameterError):
        calculate("tolerance_lookup_iso", diameter_mm=50.0)
    with pytest.raises(MissingParameterError):
        calculate("tolerance_lookup_iso", fit_class="H7")


def test_input_out_of_range_raises_specific_error():
    with pytest.raises(InputOutOfRangeError):
        calculate("tolerance_lookup_iso", diameter_mm=-1.0, fit_class="H7")
    with pytest.raises(InputOutOfRangeError):
        calculate("tolerance_lookup_iso", diameter_mm=10000.0, fit_class="H7")


def test_calculation_errors_subclass_calculation_error():
    assert issubclass(UnknownMethodError, CalculationError)
    assert issubclass(MissingParameterError, CalculationError)
    assert issubclass(InputOutOfRangeError, CalculationError)
