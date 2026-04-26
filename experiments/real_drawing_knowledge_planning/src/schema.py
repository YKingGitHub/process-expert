"""Validation helpers for real drawing planning fixtures."""

from __future__ import annotations


DRAWING_REQUIRED = {
    "source_file",
    "extraction_mode",
    "part",
    "overall_geometry",
    "dimensions",
    "features",
    "datums",
    "geometric_tolerances",
    "surface_roughness",
    "technical_requirements",
    "manufacturing_notes",
    "warnings",
}
DIM_REQUIRED = {"name", "value", "unit", "tolerance", "source_text"}
FEATURE_REQUIRED = {"name", "feature_type", "description", "related_dimensions", "source_text"}
DATUM_REQUIRED = {"name", "description", "source_text"}
GTOL_REQUIRED = {"type", "value", "datums", "applies_to", "source_text"}
RA_REQUIRED = {"value", "applies_to", "source_text"}


def validate_drawing_analysis(payload: dict) -> list[dict]:
    errors: list[dict] = []
    require_keys(payload, DRAWING_REQUIRED, "$", errors)
    validate_list(payload.get("dimensions"), "$.dimensions", DIM_REQUIRED, errors)
    validate_list(payload.get("features"), "$.features", FEATURE_REQUIRED, errors)
    validate_list(payload.get("datums"), "$.datums", DATUM_REQUIRED, errors)
    validate_list(payload.get("geometric_tolerances"), "$.geometric_tolerances", GTOL_REQUIRED, errors)
    validate_list(payload.get("surface_roughness"), "$.surface_roughness", RA_REQUIRED, errors)
    for key in ("technical_requirements", "manufacturing_notes", "warnings"):
        if not isinstance(payload.get(key), list):
            errors.append({"path": f"$.{key}", "code": "not_list"})
    return errors


def validate_reference_route(payload: dict) -> list[dict]:
    errors: list[dict] = []
    require_keys(payload, {"source_file", "source_type", "operations"}, "$", errors)
    operations = payload.get("operations")
    if not isinstance(operations, list):
        errors.append({"path": "$.operations", "code": "not_list"})
        return errors
    for index, operation in enumerate(operations):
        path = f"$.operations[{index}]"
        require_keys(operation, {"step_no", "operation", "summary"}, path, errors)
    return errors


def require_keys(obj: object, keys: set[str], path: str, errors: list[dict]) -> None:
    if not isinstance(obj, dict):
        errors.append({"path": path, "code": "not_object"})
        return
    missing = sorted(keys - set(obj.keys()))
    if missing:
        errors.append({"path": path, "code": "missing_keys", "missing": missing})


def validate_list(value: object, path: str, required_keys: set[str], errors: list[dict]) -> None:
    if not isinstance(value, list):
        errors.append({"path": path, "code": "not_list"})
        return
    for index, item in enumerate(value):
        require_keys(item, required_keys, f"{path}[{index}]", errors)
