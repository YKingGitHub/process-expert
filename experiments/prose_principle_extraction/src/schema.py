"""Validation for source-PDF prose principle extraction JSON."""

from __future__ import annotations


REQUIRED_TOP_LEVEL = {"source_page", "page_title", "principle_records", "warnings"}
REQUIRED_PRINCIPLE = {
    "id",
    "topic",
    "principle_type",
    "principle_text",
    "applicable_scenario",
    "source_text",
    "evidence_region",
    "confidence",
    "tags",
    "quality_flags",
}
VALID_PRINCIPLE_TYPES = {
    "inspection_method",
    "datum_selection",
    "operation_sequence",
    "thin_wall_processing",
    "heat_treatment_arrangement",
    "process_route_planning",
    "unknown",
}


def validate_principle_payload(payload: dict) -> list[dict]:
    errors: list[dict] = []
    require_keys(payload, REQUIRED_TOP_LEVEL, "$", errors)

    records = payload.get("principle_records")
    if not isinstance(records, list):
        errors.append({"path": "$.principle_records", "code": "not_list"})
        return errors

    for index, record in enumerate(records):
        path = f"$.principle_records[{index}]"
        if not isinstance(record, dict):
            errors.append({"path": path, "code": "not_object"})
            continue
        require_keys(record, REQUIRED_PRINCIPLE, path, errors)
        validate_string(record.get("id"), f"{path}.id", errors)
        validate_string(record.get("topic"), f"{path}.topic", errors)
        validate_string(record.get("principle_text"), f"{path}.principle_text", errors)
        validate_string(record.get("source_text"), f"{path}.source_text", errors)
        validate_string_list(record.get("tags"), f"{path}.tags", errors)
        validate_string_list(record.get("quality_flags"), f"{path}.quality_flags", errors)
        validate_confidence(record.get("confidence"), f"{path}.confidence", errors)
        if record.get("principle_type") not in VALID_PRINCIPLE_TYPES:
            errors.append(
                {
                    "path": f"{path}.principle_type",
                    "code": "invalid_principle_type",
                    "actual": record.get("principle_type"),
                }
            )

    if not isinstance(payload.get("warnings"), list):
        errors.append({"path": "$.warnings", "code": "not_list"})

    return errors


def require_keys(obj: dict, keys: set[str], path: str, errors: list[dict]) -> None:
    missing = sorted(keys - set(obj.keys()))
    if missing:
        errors.append({"path": path, "code": "missing_keys", "missing": missing})


def validate_string(value: object, path: str, errors: list[dict]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append({"path": path, "code": "empty_or_not_string"})


def validate_string_list(value: object, path: str, errors: list[dict]) -> None:
    if not isinstance(value, list):
        errors.append({"path": path, "code": "not_list"})
        return
    if any(not isinstance(item, str) for item in value):
        errors.append({"path": path, "code": "contains_non_string"})


def validate_confidence(value: object, path: str, errors: list[dict]) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append({"path": path, "code": "not_number"})
        return
    if value < 0 or value > 1:
        errors.append({"path": path, "code": "out_of_range"})
