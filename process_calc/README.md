# `process_calc` — deterministic engineering-calculation layer

This module is the production successor of `poc_process_calc.py`. It exposes
one entry point — `calculate(method_id, **params)` — that returns a uniform
shape regardless of which calculation ran. The agent calls it instead of
asking an LLM to do arithmetic.

## Public contract (frozen at Sprint C Phase 1)

```python
from process_calc import calculate

result = calculate("tolerance_lookup_iso", diameter_mm=50.0, fit_class="H7")
# {
#   "method_id": "tolerance_lookup_iso",
#   "result": {"upper_deviation_um": 25, "lower_deviation_um": 0, "tolerance_um": 25, ...},
#   "unit": "μm",
#   "steps": ["Identify size segment for φ50.0 mm: 30-50 mm", "Look up IT7 ...", ...],
#   "formula": "upper = +IT, lower = 0  (ISO 286-1, hole H); IT values per ISO 286-1:2010 §6 Table 1",
#   "warnings": [],
#   "verified": True,
#   "implementation_status": "verified"
# }
```

Every method in `METHOD_REGISTRY` returns these eight fields. Subsequent
Sprint C-2 / C-3 rounds add methods without changing this shape.

## Phase 1 methods (5)

| `method_id` | Module | Verified by |
|---|---|---|
| `tolerance_lookup_iso` | `tolerance_lookup.py` | ISO 286-1 H7/h6/g6/H8 textbook values for φ25, φ50, φ100 |
| `closed_loop_basic_size` | `dimension_chain.py` | textbook §3.2 simple example (A=30 +0/-0.05 inc, B=5 +0.05/0 dec → closed=25) |
| `extreme_tolerance` | `dimension_chain.py` | textbook §3.2 (closed_es=0, closed_ei=-0.10, T=0.10) |
| `process_dimension_reverse` | `dimension_chain.py` | textbook p.91 spirit (final 50 + [0.5, 1.5, 2.0] shaft → blank 54.0) |
| `finish_to_grind_allowance` | `machining_allowance.py` | textbook p.108 缸套 (φ279.2 → φ280.0 → 0.4 mm single-side) |

## Errors

```python
from process_calc import (
    CalculationError,           # base
    UnknownMethodError,         # method_id not in METHOD_REGISTRY
    MissingParameterError,      # required parameter absent
    InputOutOfRangeError,       # value outside supported domain
)
```

All four subclasses share `error.code` (string) and `error.message`.

## How to add a new method

1. Implement `def my_method(**params) -> dict` in a topical module (or
   create one). Use `process_calc.build_result(...)` to package the return
   payload — never construct the dict by hand.
2. Register in `process_calc/method_registry.py`:
   ```python
   METHOD_REGISTRY["my_method_id"] = my_method
   ```
3. Add at least one textbook-example unit test in
   `tests/test_process_calc/`. Without one, `verified` should stay `False`
   and `implementation_status` should be `"implemented"` (not `"verified"`).

## Boundary

`process_calc` does not access SQLite, the network, or any external state.
It is pure-function arithmetic verifiable in CI. This is intentional —
the agent treats `calculate()` as a known-good calculator, and any
calculation that depends on external context belongs in a higher layer
(e.g. the agent itself reads context, then passes structured params to
`calculate`).

The Sprint C Phase 1 design (`design.md` next to this README) freezes the
return shape and the five Phase 1 methods. Subsequent rounds (Sprint C-2+)
extend the registry toward the ~34 methods catalogued in the 04-26
method inventory.

## Reproduce

```bash
# Run process_calc unit tests
python3 -m pytest tests/test_process_calc -q

# Full project regression
python3 -m pytest experiments/ tests/ -q

# Smoke check: φ50 H7 deviation lookup
python3 -c "
from process_calc import calculate
import json
r = calculate('tolerance_lookup_iso', diameter_mm=50.0, fit_class='H7')
print(json.dumps(r, indent=2, ensure_ascii=False))
"
```
