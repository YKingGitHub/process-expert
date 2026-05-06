"""Machining-allowance calculations.

Phase 1 implements the textbook p.108 缸套 finish-to-grind allowance pattern
verified by the existing ``experiments/calculation_ready_extraction``
smoke test. Future Phase 2 may add blank-to-finished, rough-to-semifinish
and other allowance pairs once textbook examples are catalogued.
"""

from __future__ import annotations

from process_calc.errors import InputOutOfRangeError
from process_calc.result import build_result


_VALID_SURFACES = {"inner", "outer"}


def calculate_finish_to_grind_allowance(
    predecessor_diameter_mm: float,
    successor_diameter_mm: float,
    surface: str = "outer",
) -> dict:
    """Compute the finish-turn-to-grind diameter allowance and single-side
    allowance for one surface (inner or outer).

    For an outer surface the predecessor (finish-turn) diameter is **larger**
    than the successor (grind) diameter; for an inner surface it is smaller.
    The diameter allowance is always reported as the absolute difference and
    the single-side allowance is half of it.
    """
    if surface not in _VALID_SURFACES:
        raise InputOutOfRangeError(
            f"surface must be one of {sorted(_VALID_SURFACES)}, got {surface!r}"
        )
    if predecessor_diameter_mm <= 0 or successor_diameter_mm <= 0:
        raise InputOutOfRangeError(
            "diameters must be positive: "
            f"predecessor={predecessor_diameter_mm}, successor={successor_diameter_mm}"
        )

    expected_sign = -1 if surface == "outer" else 1
    diff = successor_diameter_mm - predecessor_diameter_mm
    if diff * expected_sign < 0:
        # Direction inconsistent with surface kind. Continue but warn.
        warning = {
            "code": "direction_inconsistent_with_surface",
            "message": (
                f"For an {surface} surface the {'predecessor>successor' if surface == 'outer' else 'predecessor<successor'} "
                "convention is expected; got opposite. Allowance computed from absolute "
                "diameter difference."
            ),
        }
        warnings = [warning]
    else:
        warnings = []

    diameter_allowance = round(abs(diff), 4)
    single_side = round(diameter_allowance / 2, 4)

    steps = [
        f"surface={surface}; predecessor_diameter={predecessor_diameter_mm} mm; "
        f"successor_diameter={successor_diameter_mm} mm",
        f"diameter_allowance = |successor - predecessor| = "
        f"|{successor_diameter_mm} - {predecessor_diameter_mm}| = {diameter_allowance}",
        f"single_side_allowance = diameter_allowance / 2 = {single_side}",
    ]
    return build_result(
        method_id="finish_to_grind_allowance",
        result={
            "surface": surface,
            "predecessor_diameter_mm": predecessor_diameter_mm,
            "successor_diameter_mm": successor_diameter_mm,
            "diameter_allowance_mm": diameter_allowance,
            "single_side_allowance_mm": single_side,
        },
        unit="mm",
        steps=steps,
        formula="diameter_allowance = |successor - predecessor|; single_side = diameter_allowance / 2",
        warnings=warnings,
        verified=True,
        implementation_status="verified",
    )
