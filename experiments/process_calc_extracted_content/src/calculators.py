"""Deterministic calculations over reconstructed process routes."""

from __future__ import annotations

from dataclasses import dataclass

from .operation_parser import parse_operation_content
from .route_model import ProcessRoute


@dataclass(frozen=True)
class DiameterObservation:
    step_no: int
    operation_name: str
    surface: str
    value: float
    source: str


def analyze_cylinder_liner_allowance(route: ProcessRoute) -> dict:
    observations = collect_diameter_observations(route)
    inner_values = [obs.value for obs in observations if obs.surface == "inner"]
    outer_values = [obs.value for obs in observations if obs.surface == "outer"]

    warnings = []
    if not inner_values:
        warnings.append({"code": "missing_inner_diameters"})
    if not outer_values:
        warnings.append({"code": "missing_outer_diameters"})

    inner_monotonic = is_non_decreasing(inner_values)
    outer_monotonic = is_non_increasing(outer_values)

    inner_allowance = finish_to_grind_allowance(observations, surface="inner")
    outer_allowance = finish_to_grind_allowance(observations, surface="outer")

    if inner_allowance["status"] != "passed":
        warnings.append({"code": "inner_finish_to_grind_incomplete"})
    if outer_allowance["status"] != "passed":
        warnings.append({"code": "outer_finish_to_grind_incomplete"})

    return {
        "result": {
            "inner_monotonic_non_decreasing": inner_monotonic,
            "outer_monotonic_non_increasing": outer_monotonic,
            "inner_finish_to_grind_allowance": inner_allowance,
            "outer_finish_to_grind_allowance": outer_allowance,
        },
        "unit": "mm",
        "formula": "diameter_allowance = abs(grind_diameter - finish_diameter); single_side = diameter_allowance / 2",
        "steps": [
            "Parse explicit diameters from each operation row.",
            "Classify each diameter as inner or outer from nearby operation text.",
            "Check inner diameters are non-decreasing and outer diameters are non-increasing.",
            "Compare last finish-machining diameter with first grinding diameter for each surface.",
        ],
        "warnings": warnings,
    }


def analyze_explicit_grinding_allowance(route: ProcessRoute) -> dict:
    """Link explicit grinding allowance mentions to later grinding steps.

    This intentionally does not claim a numeric pass unless both pre-grinding and
    final dimensions are structurally available. For many process-card rows, the
    text says "reserve grinding allowance 0.8mm" but the final value is described
    as "to drawing requirement", which is not enough for an independent check.
    """

    allowance_mentions = []
    grind_steps = [step for step in route.steps if "磨" in step.operation_name]
    for step in route.steps:
        parsed = parse_operation_content(step.operation_content)
        for allowance in parsed["allowances"]:
            if "磨" not in allowance["source"]:
                continue
            allowance_mentions.append(
                {
                    "step_no": step.step_no,
                    "operation_name": step.operation_name,
                    "value": allowance["value"],
                    "source": allowance["source"],
                    "later_grinding_steps": [
                        grind.step_no for grind in grind_steps if grind.step_no > step.step_no
                    ],
                }
            )

    warnings = []
    if not allowance_mentions:
        warnings.append({"code": "missing_explicit_grinding_allowance"})
    for mention in allowance_mentions:
        if not mention["later_grinding_steps"]:
            warnings.append(
                {
                    "code": "allowance_without_later_grinding_step",
                    "step_no": mention["step_no"],
                }
            )

    status = (
        "needs_more_structured_final_dimension"
        if allowance_mentions
        else "missing_input"
    )
    return {
        "result": {
            "status": status,
            "explicit_allowances": allowance_mentions,
        },
        "unit": "mm",
        "formula": "guarded check only; explicit allowance requires structured pre-grind and final dimensions for numeric verification",
        "steps": [
            "Parse explicit grinding allowance mentions.",
            "Find later grinding operations in the same route.",
            "Return guarded incomplete status unless independent final dimensions are available.",
        ],
        "warnings": warnings,
    }


def collect_diameter_observations(route: ProcessRoute) -> list[DiameterObservation]:
    observations = []
    for step in route.steps:
        parsed = parse_operation_content(step.operation_content)
        for diameter in parsed["diameters"]:
            if diameter["surface"] == "unknown":
                continue
            observations.append(
                DiameterObservation(
                    step_no=step.step_no,
                    operation_name=step.operation_name,
                    surface=diameter["surface"],
                    value=diameter["value"],
                    source=diameter["source"],
                )
            )
    return observations


def finish_to_grind_allowance(
    observations: list[DiameterObservation], surface: str
) -> dict:
    finish = [
        obs
        for obs in observations
        if obs.surface == surface and obs.operation_name in ("精车", "精镗")
    ]
    grind = [
        obs
        for obs in observations
        if obs.surface == surface and "磨" in obs.operation_name
    ]
    if not finish or not grind:
        return {"status": "needs_more_structured_final_dimension"}

    last_finish = max(finish, key=lambda obs: obs.step_no)
    later_grind = [obs for obs in grind if obs.step_no > last_finish.step_no]
    if not later_grind:
        return {"status": "needs_more_structured_final_dimension"}

    first_grind = min(later_grind, key=lambda obs: obs.step_no)
    diameter_allowance = abs(first_grind.value - last_finish.value)
    return {
        "status": "passed",
        "diameter_allowance": round(diameter_allowance, 6),
        "single_side_allowance": round(diameter_allowance / 2, 6),
        "finish_step": last_finish.step_no,
        "finish_source": last_finish.source,
        "grind_step": first_grind.step_no,
        "grind_source": first_grind.source,
    }


def is_non_decreasing(values: list[float]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))


def is_non_increasing(values: list[float]) -> bool:
    return all(left >= right for left, right in zip(values, values[1:]))
