"""Method registry — maps stable ``method_id`` strings to callables.

Adding a new Sprint-C method:
    1. Implement ``def my_method(**params) -> dict`` in a topical module
       (e.g. ``process_calc/dimension_chain.py``). Use ``build_result`` to
       package the return.
    2. Register it here with a ``method_id`` that follows the naming policy:
       ``{module}_{operation}`` lowercase snake_case (e.g.
       ``tolerance_lookup_iso``, ``closed_loop_basic_size``).
    3. Add at least one textbook-example unit test under
       ``tests/test_process_calc/`` to qualify ``verified=True``.
"""

from __future__ import annotations

from typing import Callable

from process_calc.dimension_chain import (
    calculate_closed_loop_basic_size,
    calculate_extreme_tolerance,
    calculate_process_dimension_reverse,
)
from process_calc.lookup_kb import (
    lookup_cutting_params,
    lookup_economic_precision,
    lookup_machining_allowance,
    lookup_method_position_error,
    lookup_path_precision,
)
from process_calc.machining_allowance import calculate_finish_to_grind_allowance
from process_calc.tolerance_lookup import calculate_tolerance_lookup_iso
from process_calc.work_hardening import calculate_work_hardening_ratio


METHOD_REGISTRY: dict[str, Callable[..., dict]] = {
    "tolerance_lookup_iso": calculate_tolerance_lookup_iso,
    "closed_loop_basic_size": calculate_closed_loop_basic_size,
    "extreme_tolerance": calculate_extreme_tolerance,
    "process_dimension_reverse": calculate_process_dimension_reverse,
    "finish_to_grind_allowance": calculate_finish_to_grind_allowance,
    "work_hardening_ratio": calculate_work_hardening_ratio,
    "lookup_economic_precision": lookup_economic_precision,
    "lookup_path_precision": lookup_path_precision,
    "lookup_method_position_error": lookup_method_position_error,
    "lookup_cutting_params": lookup_cutting_params,
    "lookup_machining_allowance": lookup_machining_allowance,
}
