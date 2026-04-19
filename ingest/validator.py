"""Validator — Pydantic schema validation for extracted records."""

from pydantic import ValidationError

from ingest.schemas import (
    EquipmentSpec, ProcessParam, SurfaceStandard, ToleranceFit,
)


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


def validate_tolerance(raw: dict) -> tuple[bool, any]:
    """Validate a raw dict against ToleranceFit schema."""
    try:
        model = ToleranceFit.model_validate(raw)
        return True, model
    except ValidationError as e:
        return False, str(e)


def validate_equipment(raw: dict) -> tuple[bool, any]:
    """Validate a raw dict against EquipmentSpec schema."""
    try:
        model = EquipmentSpec.model_validate(raw)
        return True, model
    except ValidationError as e:
        return False, str(e)


def validate_surface(raw: dict) -> tuple[bool, any]:
    """Validate a raw dict against SurfaceStandard schema."""
    try:
        model = SurfaceStandard.model_validate(raw)
        return True, model
    except ValidationError as e:
        return False, str(e)
