"""Dimension-chain extreme-method calculations + process-dimension reverse.

Based on the textbook §3.2 (尺寸链极值法) and p.91 (工序尺寸反推) examples.
The POC equivalents in ``poc_process_calc.py`` are the original prototypes;
this module is the production version with the uniform return shape.
"""

from __future__ import annotations

from process_calc.errors import InputOutOfRangeError
from process_calc.result import build_result


_VALID_ROLES = {"increasing", "decreasing"}
_VALID_DIRECTIONS = {"shaft", "hole"}


def calculate_closed_loop_basic_size(components: list[dict]) -> dict:
    """Closed-loop basic size (封闭环基本尺寸) per the extreme method.

    closed_basic = Σ(increasing.basic_dim) - Σ(decreasing.basic_dim)
    """
    _validate_components(components)
    increasing = sum(c["basic_dim"] for c in components if c["role"] == "increasing")
    decreasing = sum(c["basic_dim"] for c in components if c["role"] == "decreasing")
    closed = round(increasing - decreasing, 6)
    steps = [
        f"Sum increasing components: {increasing}",
        f"Sum decreasing components: {decreasing}",
        f"closed_basic = {increasing} - {decreasing} = {closed}",
    ]
    return build_result(
        method_id="closed_loop_basic_size",
        result={
            "closed_loop_basic_dim": closed,
            "increasing_sum": round(increasing, 6),
            "decreasing_sum": round(decreasing, 6),
        },
        unit="mm",
        steps=steps,
        formula="closed_basic = Σ(increasing.basic) - Σ(decreasing.basic)",
        verified=True,
        implementation_status="verified",
    )


def calculate_extreme_tolerance(components: list[dict]) -> dict:
    """Closed-loop tolerance (封闭环极值公差) per the extreme method.

    closed_es = Σ(increasing.es) - Σ(decreasing.ei)
    closed_ei = Σ(increasing.ei) - Σ(decreasing.es)
    closed_tolerance = closed_es - closed_ei
    """
    _validate_components(components, require_deviations=True)
    inc_es = sum(c["es"] for c in components if c["role"] == "increasing")
    inc_ei = sum(c["ei"] for c in components if c["role"] == "increasing")
    dec_es = sum(c["es"] for c in components if c["role"] == "decreasing")
    dec_ei = sum(c["ei"] for c in components if c["role"] == "decreasing")
    closed_es = round(inc_es - dec_ei, 6)
    closed_ei = round(inc_ei - dec_es, 6)
    closed_tolerance = round(closed_es - closed_ei, 6)
    inc_basic = sum(c["basic_dim"] for c in components if c["role"] == "increasing")
    dec_basic = sum(c["basic_dim"] for c in components if c["role"] == "decreasing")
    closed_basic = round(inc_basic - dec_basic, 6)
    steps = [
        f"closed_es = Σ(inc.es) - Σ(dec.ei) = {inc_es} - {dec_ei} = {closed_es}",
        f"closed_ei = Σ(inc.ei) - Σ(dec.es) = {inc_ei} - {dec_es} = {closed_ei}",
        f"closed_tolerance = closed_es - closed_ei = {closed_es} - {closed_ei} = {closed_tolerance}",
    ]
    return build_result(
        method_id="extreme_tolerance",
        result={
            "closed_loop_basic_dim": closed_basic,
            "closed_loop_es": closed_es,
            "closed_loop_ei": closed_ei,
            "closed_loop_tolerance": closed_tolerance,
            "max_dimension": round(closed_basic + closed_es, 6),
            "min_dimension": round(closed_basic + closed_ei, 6),
        },
        unit="mm",
        steps=steps,
        formula="closed_es = Σ(inc.es) - Σ(dec.ei); closed_ei = Σ(inc.ei) - Σ(dec.es)",
        verified=True,
        implementation_status="verified",
    )


def calculate_process_dimension_reverse(
    final_dimension_mm: float,
    allowances_mm: list[float],
    direction: str = "shaft",
) -> dict:
    """Reverse-compute upstream process dimensions from the final size.

    For a shaft (尺寸越加工越小), each upstream step is larger:
        prev = current + allowance
    For a hole (尺寸越加工越大), each upstream step is smaller:
        prev = current - allowance

    Returns the per-step dimensions in the same order as ``allowances_mm``
    (which lists allowances starting from the latest pass and going back).
    """
    if direction not in _VALID_DIRECTIONS:
        raise InputOutOfRangeError(
            f"direction must be one of {sorted(_VALID_DIRECTIONS)}, got {direction!r}"
        )
    if not allowances_mm:
        raise InputOutOfRangeError("allowances_mm must contain at least one value")
    for allowance in allowances_mm:
        if allowance <= 0:
            raise InputOutOfRangeError(
                f"all allowances must be positive, got {allowance}"
            )

    process_dims: list[float] = []
    current = final_dimension_mm
    for allowance in allowances_mm:
        if direction == "shaft":
            current = current + allowance
        else:
            current = current - allowance
        process_dims.append(round(current, 4))
    blank_dim = process_dims[-1]
    total_allowance = round(sum(allowances_mm), 4)
    steps = [
        f"final_dimension={final_dimension_mm} mm; direction={direction}",
        f"apply {len(allowances_mm)} allowances in reverse order: {allowances_mm}",
        f"per-step dimensions (latest -> earliest): {process_dims}",
        f"blank_dimension = {blank_dim} mm; total_allowance = {total_allowance} mm",
    ]
    formula = (
        "shaft: prev = current + allowance; "
        "hole:  prev = current - allowance"
    )
    return build_result(
        method_id="process_dimension_reverse",
        result={
            "final_dimension_mm": final_dimension_mm,
            "process_dimensions_mm": process_dims,
            "blank_dimension_mm": blank_dim,
            "total_allowance_mm": total_allowance,
            "step_count": len(allowances_mm),
            "direction": direction,
        },
        unit="mm",
        steps=steps,
        formula=formula,
        verified=True,
        implementation_status="verified",
    )


def _validate_components(
    components: list[dict],
    *,
    require_deviations: bool = False,
) -> None:
    if not components:
        raise InputOutOfRangeError("components must contain at least one entry")
    for index, component in enumerate(components):
        for required in ("basic_dim", "role"):
            if required not in component:
                raise InputOutOfRangeError(
                    f"component[{index}] missing required field {required!r}"
                )
        if component["role"] not in _VALID_ROLES:
            raise InputOutOfRangeError(
                f"component[{index}].role must be one of {sorted(_VALID_ROLES)}, "
                f"got {component['role']!r}"
            )
        if require_deviations:
            for required in ("es", "ei"):
                if required not in component:
                    raise InputOutOfRangeError(
                        f"component[{index}] missing required deviation field {required!r}"
                    )
                if component["es"] < component["ei"]:
                    raise InputOutOfRangeError(
                        f"component[{index}] has es < ei (upper < lower): inconsistent"
                    )
