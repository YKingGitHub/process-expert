"""``calculate(method_id, **params)`` — public entry point of process_calc.

The dispatcher:
  1. Looks ``method_id`` up in :data:`process_calc.METHOD_REGISTRY`.
  2. Inspects the target callable's signature to identify required params
     (positional-or-keyword without default), and raises
     :class:`MissingParameterError` for any absent required param.
  3. Forwards everything else to the callable. The callable is responsible
     for raising :class:`InputOutOfRangeError` when a value is present but
     outside the supported domain.
"""

from __future__ import annotations

import inspect
from typing import Any

from process_calc.errors import MissingParameterError, UnknownMethodError
from process_calc.method_registry import METHOD_REGISTRY


def calculate(method_id: str, **params: Any) -> dict:
    if method_id not in METHOD_REGISTRY:
        raise UnknownMethodError(
            f"Unknown method_id {method_id!r}. "
            f"Registered methods: {sorted(METHOD_REGISTRY)}"
        )
    callable_ = METHOD_REGISTRY[method_id]
    _check_required_params(method_id, callable_, params)
    return callable_(**params)


def _check_required_params(
    method_id: str, callable_: Any, params: dict[str, Any]
) -> None:
    sig = inspect.signature(callable_)
    missing: list[str] = []
    for name, parameter in sig.parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Parameter.empty and name not in params:
            missing.append(name)
    if missing:
        raise MissingParameterError(
            f"{method_id} requires parameter(s) {missing} but none provided"
        )
