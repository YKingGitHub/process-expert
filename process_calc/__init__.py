"""``process_calc`` — deterministic engineering-calculation layer.

Public entry point: :func:`process_calc.calculate`. The agent calls this
instead of asking an LLM to perform arithmetic. Every method returns a
uniform shape (``result``, ``unit``, ``steps``, ``formula``, ``warnings``,
``verified``, ``implementation_status``) so callers can render derivations
without method-specific code.

Phase 1 ships five methods (see ``design.md``). The contract is frozen for
Phase 1; subsequent rounds add methods without changing the return shape.
"""

from process_calc.dispatcher import calculate
from process_calc.errors import (
    CalculationError,
    InputOutOfRangeError,
    MissingParameterError,
    UnknownMethodError,
)
from process_calc.method_registry import METHOD_REGISTRY
from process_calc.result import CalculationResult, build_result

__all__ = [
    "METHOD_REGISTRY",
    "CalculationError",
    "CalculationResult",
    "InputOutOfRangeError",
    "MissingParameterError",
    "UnknownMethodError",
    "build_result",
    "calculate",
]
