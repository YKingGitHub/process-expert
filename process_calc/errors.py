"""Exception hierarchy for ``process_calc``."""

from __future__ import annotations


class CalculationError(Exception):
    """Base class for any deterministic-calculation failure."""

    code = "calculation_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class UnknownMethodError(CalculationError):
    """Raised when ``calculate(method_id, ...)`` references a method_id that is
    not registered in ``METHOD_REGISTRY``."""

    code = "unknown_method"


class MissingParameterError(CalculationError):
    """Raised when a required parameter is absent from the caller's kwargs."""

    code = "missing_parameter"


class InputOutOfRangeError(CalculationError):
    """Raised when a parameter is present but its value lies outside the
    method's supported domain (e.g., diameter < 0.5 mm or > 500 mm for the
    ISO 286-1 lookup)."""

    code = "input_out_of_range"
