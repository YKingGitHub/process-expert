"""Lightweight validation for VLM process-card JSON."""

from __future__ import annotations


REQUIRED_TOP_LEVEL = {"source_page", "page_title", "cards", "warnings"}
REQUIRED_CARD = {
    "part_name",
    "table_no",
    "table_title",
    "is_continuation",
    "continuation_of",
    "technical_requirements",
    "steps",
}
REQUIRED_STEP = {
    "step_no",
    "operation_name",
    "operation_content",
    "equipment",
    "dimensions",
    "allowances",
}
REQUIRED_DIMENSION = {
    "surface",
    "nominal",
    "unit",
    "upper_deviation",
    "lower_deviation",
    "tolerance_text",
    "source_text",
}
REQUIRED_ALLOWANCE = {
    "allowance_type",
    "value",
    "max_value",
    "unit",
    "source_text",
}


def validate_process_card_payload(payload: dict) -> list[dict]:
    errors = []
    require_keys(payload, REQUIRED_TOP_LEVEL, "$", errors)

    cards = payload.get("cards")
    if not isinstance(cards, list):
        errors.append({"path": "$.cards", "code": "not_list"})
        return errors

    for card_index, card in enumerate(cards):
        card_path = f"$.cards[{card_index}]"
        if not isinstance(card, dict):
            errors.append({"path": card_path, "code": "not_object"})
            continue
        require_keys(card, REQUIRED_CARD, card_path, errors)
        validate_type(card.get("is_continuation"), bool, f"{card_path}.is_continuation", errors)
        validate_string_list(
            card.get("technical_requirements"),
            f"{card_path}.technical_requirements",
            errors,
        )
        validate_steps(card.get("steps"), f"{card_path}.steps", errors)

    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        errors.append({"path": "$.warnings", "code": "not_list"})

    return errors


def validate_steps(steps: object, path: str, errors: list[dict]) -> None:
    if not isinstance(steps, list):
        errors.append({"path": path, "code": "not_list"})
        return

    for step_index, step in enumerate(steps):
        step_path = f"{path}[{step_index}]"
        if not isinstance(step, dict):
            errors.append({"path": step_path, "code": "not_object"})
            continue
        require_keys(step, REQUIRED_STEP, step_path, errors)
        validate_type(step.get("step_no"), int, f"{step_path}.step_no", errors)
        validate_dimensions(step.get("dimensions"), f"{step_path}.dimensions", errors)
        validate_allowances(step.get("allowances"), f"{step_path}.allowances", errors)


def validate_dimensions(dimensions: object, path: str, errors: list[dict]) -> None:
    if not isinstance(dimensions, list):
        errors.append({"path": path, "code": "not_list"})
        return

    for index, dimension in enumerate(dimensions):
        item_path = f"{path}[{index}]"
        if not isinstance(dimension, dict):
            errors.append({"path": item_path, "code": "not_object"})
            continue
        require_keys(dimension, REQUIRED_DIMENSION, item_path, errors)
        validate_number_or_none(dimension.get("nominal"), f"{item_path}.nominal", errors)
        validate_number_or_none(
            dimension.get("upper_deviation"), f"{item_path}.upper_deviation", errors
        )
        validate_number_or_none(
            dimension.get("lower_deviation"), f"{item_path}.lower_deviation", errors
        )


def validate_allowances(allowances: object, path: str, errors: list[dict]) -> None:
    if not isinstance(allowances, list):
        errors.append({"path": path, "code": "not_list"})
        return

    for index, allowance in enumerate(allowances):
        item_path = f"{path}[{index}]"
        if not isinstance(allowance, dict):
            errors.append({"path": item_path, "code": "not_object"})
            continue
        require_keys(allowance, REQUIRED_ALLOWANCE, item_path, errors)
        validate_number_or_none(allowance.get("value"), f"{item_path}.value", errors)
        validate_number_or_none(
            allowance.get("max_value"), f"{item_path}.max_value", errors
        )


def require_keys(obj: dict, keys: set[str], path: str, errors: list[dict]) -> None:
    missing = sorted(keys - set(obj.keys()))
    if missing:
        errors.append({"path": path, "code": "missing_keys", "missing": missing})


def validate_type(value: object, expected_type: type, path: str, errors: list[dict]) -> None:
    if not isinstance(value, expected_type):
        errors.append({"path": path, "code": "wrong_type", "expected": expected_type.__name__})


def validate_string_list(value: object, path: str, errors: list[dict]) -> None:
    if not isinstance(value, list):
        errors.append({"path": path, "code": "not_list"})
        return
    if any(not isinstance(item, str) for item in value):
        errors.append({"path": path, "code": "contains_non_string"})


def validate_number_or_none(value: object, path: str, errors: list[dict]) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append({"path": path, "code": "not_number_or_null"})
