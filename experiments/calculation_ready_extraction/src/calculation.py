"""Deterministic calculations from VLM process-card JSON."""

from __future__ import annotations

from .route_merge import Route


def calculate_cylinder_liner_allowance(route: Route) -> dict:
    observations = []
    for step in route.steps:
        for dimension in step.get("dimensions", []):
            if dimension.get("surface") not in ("inner", "outer"):
                continue
            observations.append(
                {
                    "step_no": step["step_no"],
                    "operation_name": step["operation_name"],
                    "surface": dimension["surface"],
                    "nominal": float(dimension["nominal"]),
                    "source_text": dimension.get("source_text"),
                }
            )

    inner = finish_to_grind(observations, "inner")
    outer = finish_to_grind(observations, "outer")
    warnings = []
    if inner["status"] != "passed":
        warnings.append({"code": "inner_allowance_not_ready"})
    if outer["status"] != "passed":
        warnings.append({"code": "outer_allowance_not_ready"})

    return {
        "result": {
            "inner_finish_to_grind_allowance": inner,
            "outer_finish_to_grind_allowance": outer,
        },
        "unit": "mm",
        "formula": "diameter_allowance = abs(grind_diameter - finish_diameter); single_side = diameter_allowance / 2",
        "steps": [
            "Read accepted VLM dimensions from the cylinder liner route.",
            "Find the latest finish-turning dimension before grinding for each surface.",
            "Find the first later grinding dimension for each surface.",
            "Calculate diameter allowance and single-side allowance.",
        ],
        "warnings": warnings,
    }


def finish_to_grind(observations: list[dict], surface: str) -> dict:
    finish = [
        item
        for item in observations
        if item["surface"] == surface and item["operation_name"] in ("精车", "精镗")
    ]
    grind = [
        item
        for item in observations
        if item["surface"] == surface and "磨" in item["operation_name"]
    ]
    if not finish or not grind:
        return {"status": "not_ready_missing_dimensions"}

    last_finish = max(finish, key=lambda item: item["step_no"])
    later_grind = [item for item in grind if item["step_no"] > last_finish["step_no"]]
    if not later_grind:
        return {"status": "not_ready_missing_later_grinding_dimension"}

    first_grind = min(later_grind, key=lambda item: item["step_no"])
    diameter_allowance = abs(first_grind["nominal"] - last_finish["nominal"])
    return {
        "status": "passed",
        "finish_step": last_finish["step_no"],
        "finish_source": last_finish["source_text"],
        "grind_step": first_grind["step_no"],
        "grind_source": first_grind["source_text"],
        "diameter_allowance": round(diameter_allowance, 6),
        "single_side_allowance": round(diameter_allowance / 2, 6),
    }
