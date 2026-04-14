"""Validator — Pydantic schema validation for extracted records."""

from pydantic import ValidationError

from ingest.schemas import ProcessParam


def validate_param(raw: dict) -> tuple[bool, any]:
    """
    Validate a raw dict against ProcessParam schema.

    Returns:
        (True, ProcessParam instance) on success
        (False, error_message: str) on failure
    """
    try:
        model = ProcessParam.model_validate(raw)
        return True, model
    except ValidationError as e:
        return False, str(e)
