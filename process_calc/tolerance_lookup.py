"""ISO 286-1 fundamental-deviation + IT-grade lookup.

Phase 1 supports fit classes ``H6 H7 H8`` (hole), ``h6 h7 h8`` (shaft),
``g6`` (shaft, common running fit) over diameter range [0.5, 500] mm.
Other letters (j/k/m/n/p…) and other grades (IT5, IT9, IT10) are deferred
to Sprint C-2.

Values are taken from ISO 286-1:2010 Annex tables (which match the older
GB/T 1800.2 tables). The lookup is exact (integer μm) — no interpolation
between size segments and no float arithmetic in the public payload.
"""

from __future__ import annotations

from process_calc.errors import InputOutOfRangeError
from process_calc.result import build_result


# IT grade values in μm by basic-size segment (mm).
# Source: ISO 286-1:2010 §6 Table 1.
_IT_TABLE: dict[str, list[tuple[float, float, int]]] = {
    "IT6": [
        (0.5, 3, 6),
        (3, 6, 8),
        (6, 10, 9),
        (10, 18, 11),
        (18, 30, 13),
        (30, 50, 16),
        (50, 80, 19),
        (80, 120, 22),
        (120, 180, 25),
        (180, 250, 29),
        (250, 315, 32),
        (315, 400, 36),
        (400, 500, 40),
    ],
    "IT7": [
        (0.5, 3, 10),
        (3, 6, 12),
        (6, 10, 15),
        (10, 18, 18),
        (18, 30, 21),
        (30, 50, 25),
        (50, 80, 30),
        (80, 120, 35),
        (120, 180, 40),
        (180, 250, 46),
        (250, 315, 52),
        (315, 400, 57),
        (400, 500, 63),
    ],
    "IT8": [
        (0.5, 3, 14),
        (3, 6, 18),
        (6, 10, 22),
        (10, 18, 27),
        (18, 30, 33),
        (30, 50, 39),
        (50, 80, 46),
        (80, 120, 54),
        (120, 180, 63),
        (180, 250, 72),
        (250, 315, 81),
        (315, 400, 89),
        (400, 500, 97),
    ],
}

# Fundamental deviation in μm by basic-size segment (mm).
# Source: ISO 286-1:2010 §5 Tables 6-8.
# H is hole with EI = 0; the upper deviation = +IT.
# h is shaft with es = 0; the lower deviation = -IT.
# g is shaft with the upper deviation as listed below (negative);
# the lower deviation = upper - IT.
_FUNDAMENTAL_DEVIATION_G: list[tuple[float, float, int]] = [
    (0.5, 3, -2),
    (3, 6, -4),
    (6, 10, -5),
    (10, 18, -6),
    (18, 30, -7),
    (30, 50, -9),
    (50, 80, -10),
    (80, 120, -12),
    (120, 180, -14),
    (180, 250, -15),
    (250, 315, -17),
    (315, 400, -18),
    (400, 500, -20),
]


SUPPORTED_FIT_CLASSES = ("H6", "H7", "H8", "h6", "h7", "h8", "g6")
DIAMETER_RANGE_MM = (0.5, 500.0)


def calculate_tolerance_lookup_iso(diameter_mm: float, fit_class: str) -> dict:
    """Return the upper/lower deviation (μm) for an ISO 286-1 fit class.

    Parameters:
      diameter_mm: nominal diameter (basic size), mm.
      fit_class:   ``H6/H7/H8`` (hole) or ``h6/h7/h8/g6`` (shaft).
    """
    _check_diameter(diameter_mm)
    _check_fit_class(fit_class)

    grade_key = f"IT{fit_class[1]}"
    it_value = _lookup_segment(_IT_TABLE[grade_key], diameter_mm)
    letter = fit_class[0]

    if letter == "H":  # hole, lower deviation = 0
        upper = it_value
        lower = 0
        formula = "upper = +IT, lower = 0  (ISO 286-1, hole H)"
    elif letter == "h":  # shaft, upper deviation = 0
        upper = 0
        lower = -it_value
        formula = "upper = 0, lower = -IT  (ISO 286-1, shaft h)"
    elif letter == "g":  # shaft, upper from fundamental-deviation table
        es = _lookup_segment(_FUNDAMENTAL_DEVIATION_G, diameter_mm)
        upper = es
        lower = es - it_value
        formula = "upper = es_g, lower = es_g - IT  (ISO 286-1, shaft g)"
    else:  # pragma: no cover — guarded by SUPPORTED_FIT_CLASSES
        raise InputOutOfRangeError(f"unsupported letter {letter!r}")

    segment = _segment_label(diameter_mm)
    steps = [
        f"Identify size segment for φ{diameter_mm} mm: {segment}",
        f"Look up {grade_key} for segment {segment}: {it_value} μm",
        f"Apply ISO 286-1 letter '{letter}' fundamental deviation rule: {formula}",
        f"Compute upper={upper} μm, lower={lower} μm, tolerance={it_value} μm",
    ]
    return build_result(
        method_id="tolerance_lookup_iso",
        result={
            "diameter_mm": diameter_mm,
            "fit_class": fit_class,
            "size_segment_mm": segment,
            "upper_deviation_um": upper,
            "lower_deviation_um": lower,
            "tolerance_um": it_value,
        },
        unit="μm",
        steps=steps,
        formula=formula + "; IT values per ISO 286-1:2010 §6 Table 1",
        verified=True,
        implementation_status="verified",
    )


def _check_diameter(diameter_mm: float) -> None:
    low, high = DIAMETER_RANGE_MM
    if diameter_mm <= 0 or diameter_mm > high or diameter_mm < low:
        raise InputOutOfRangeError(
            f"diameter_mm={diameter_mm} outside supported range "
            f"[{low}, {high}] mm"
        )


def _check_fit_class(fit_class: str) -> None:
    if fit_class not in SUPPORTED_FIT_CLASSES:
        raise InputOutOfRangeError(
            f"fit_class={fit_class!r} not supported in Phase 1. "
            f"Supported: {SUPPORTED_FIT_CLASSES}"
        )


def _lookup_segment(table: list[tuple[float, float, int]], diameter_mm: float) -> int:
    for low, high, value in table:
        if low <= diameter_mm <= high:
            return value
    raise InputOutOfRangeError(
        f"diameter_mm={diameter_mm} not covered by any segment"
    )


def _segment_label(diameter_mm: float) -> str:
    for low, high, _ in _IT_TABLE["IT7"]:
        if low <= diameter_mm <= high:
            return f"{low}-{high} mm"
    return "?"
