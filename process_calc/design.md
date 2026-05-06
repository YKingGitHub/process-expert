---
id: D-PROCESS-20260506-02-process-calc-phase1
title: PROCESS Sprint C Phase 1 — process_calc deterministic calculation layer
status: approved
approved_by_user: true
approved_date: 2026-05-06
quality_gate: plan-v1
created: 2026-05-06
workflow_baseline: A18
follows: D-PROCESS-20260506-01-capability-seed-expansion-b2
---

# Sprint C Phase 1 — `process_calc` deterministic calculation layer

## Summary

Sprint C builds `process_calc/` as a top-level Python module that the
PROCESS agent can call to perform engineering calculations deterministically
instead of relying on an LLM to do arithmetic. Phase 1 ships **the public
contract + 5 verified methods** that:

- close DCA-003 (`python_executable_tolerance_lookup`), the only remaining
  capability-eval gap after B1+B2 (`expanded_gap_count` 1 → 0)
- re-verify DCA-001/002 (`closed_loop_basic_size`, `extreme_tolerance`)
  with executable Python, not just method documentation
- demonstrate the calculation path for the cylinder-liner finish-to-grind
  allowance already extracted in `experiments/calculation_ready_extraction`

Phase 1 is the foundation. The 04-26 weekly report identified ~34 candidate
methods across 5 modules; subsequent Sprint C-2 / C-3 rounds will extend
the registry. Phase 1 freezes the public contract so later rounds add
methods without breaking callers.

## Scope (Phase 1)

Implement the following module layout:

```text
process_calc/
├── __init__.py            # exports `calculate`, `METHOD_REGISTRY`, `CalculationResult`
├── dispatcher.py          # calculate(method_id, **params) entry point
├── method_registry.py     # METHOD_REGISTRY: method_id -> callable
├── result.py              # CalculationResult dataclass + return-shape helper
├── tolerance_lookup.py    # ISO general-tolerance lookup (covers DCA-003)
├── dimension_chain.py     # closed_loop_basic_size + extreme_tolerance
├── machining_allowance.py # finish_to_grind_allowance + blank_to_finished
├── design.md              # this document
└── README.md              # how to call calculate()

tests/
└── test_process_calc/
    ├── test_dispatcher.py
    ├── test_tolerance_lookup.py
    ├── test_dimension_chain.py
    └── test_machining_allowance.py
```

Five method_ids in Phase 1:

| method_id | Module | Verified by | Covers |
|---|---|---|---|
| `tolerance_lookup_iso` | `tolerance_lookup.py` | ISO 286-1 H7/h6/g6/H8 fundamental deviation table | DCA-003 (φ50H7 上下偏差) |
| `closed_loop_basic_size` | `dimension_chain.py` | textbook §3.2 example | DCA-001 |
| `extreme_tolerance` | `dimension_chain.py` | textbook §3.2 example | DCA-002 |
| `process_dimension_reverse` | `dimension_chain.py` | textbook p.91 example | (no eval question yet, foundational) |
| `finish_to_grind_allowance` | `machining_allowance.py` | textbook p.108 缸套 example | MAP-002 (already covered in baseline; verifies route) |

Each method must have **at least one passing textbook-example unit test**
to qualify for `verified=True`. Methods without textbook examples are not
in Phase 1.

## Non-goals (deferred to Sprint C-2+)

- The remaining ~29 methods from the unified_extract.db inventory
- LLM-driven parameter extraction from natural-language questions
- Integration into Stage 1-5 production pipeline (still experimental
  evidence collection at this stage)
- Wire into Feishu / OpenClaw runtime
- Sympy/numpy adoption (Phase 1 stays on Python stdlib `math` only,
  per ADR in 04-26 weekly report)

## Public Contract (frozen for Phase 1)

```python
from process_calc import calculate

result = calculate("tolerance_lookup_iso", diameter=50.0, fit_class="H7")
# returns:
# {
#   "method_id": "tolerance_lookup_iso",
#   "result": {"upper_deviation_um": 25, "lower_deviation_um": 0, "tolerance_um": 25},
#   "unit": "μm",
#   "steps": ["..."],
#   "formula": "...",
#   "warnings": [],
#   "verified": True,
#   "implementation_status": "verified"
# }
```

Stable shape across all methods:

```text
{
  method_id: str             (echo)
  result: dict | float       (method-specific payload)
  unit: str
  steps: list[str]           (human-readable derivation)
  formula: str               (formal expression)
  warnings: list[dict]       ([] when verified, populated when accepted_with_flags)
  verified: bool             (True iff at least one textbook example is unit-tested)
  implementation_status: str (verified | implemented | prototype)
}
```

Errors raise `process_calc.CalculationError` with attribute `code` and
human-readable `message`. Invalid `method_id` raises `UnknownMethodError`.
Missing required parameter raises `MissingParameterError`. Out-of-range
input raises `InputOutOfRangeError`.

## Acceptance gates

```text
phase1_methods_verified                 = 5  (all 5 with textbook tests)
phase1_method_ids_unique                = 5  (no aliasing)
return_shape_uniform_across_methods     = yes
calculation_methods_seed_status_updated = yes (5 records -> implementation_status verified/implemented)
dca_003_now_covered                     = yes (gap_count -> 0)
no_baseline_or_b1_b2_regression         = yes
sprint_c_unit_tests_pass                = N tests, N >= 12 (multiple textbook examples per method)
overall_pytest                          = passes
```

`expanded_gap_count` after Sprint C Phase 1 should be **0/21** (only
RPL-003 remains as `not required`; FPS-003 case_records expected_family
is in CORE_FAMILIES so it should also be covered if base seed has at least
one case record matching... let me re-check FPS-003 in WO-C-004).

## Implementation sequence

| Work order | Deliverable | Tests |
|---|---|---|
| **WO-C-001** | `process_calc/{__init__, dispatcher, method_registry, result, tolerance_lookup}.py` + `test_dispatcher.py` + `test_tolerance_lookup.py` | dispatcher/return-shape contracts + ISO H7 textbook values for φ50, φ25, φ100 |
| **WO-C-002** | `dimension_chain.py` with closed_loop_basic_size + extreme_tolerance + process_dimension_reverse | textbook §3.2 dimension-chain example + p.91 process-dimension example |
| **WO-C-003** | `machining_allowance.py` with finish_to_grind_allowance + blank_to_finished_diameter_allowance | p.108 缸套 finish-to-grind verified |
| **WO-C-004** | Integration + capability seed update + README + regression | update agent_query_eval seed (5 records → implementation_status); add new CM-TOL-LOOKUP-ISO record for DCA-003; verify expanded_gap_count = 0 |

## Routing for DCA-003

DCA-003 question text: *"φ50H7 的上下偏差能否由 Python 返回 result、steps、
formula 和 warnings？"*. Base classifier currently routes to `INTENT_LOOKUP`
because of the `上下偏差` keyword. Sprint C must either:

- (a) Add a manual_boost in `KnowledgeQuery.manual_boost` so a record with
  ID containing `TOL-LOOKUP-ISO` outranks lookup hits when the question
  contains both `Python` and `H7`, OR
- (b) Add a `_match_tolerance_calculation` route in `ExpandedKnowledgeQuery`
  that intercepts `Python` + `H7/H8/g6` + `result.*steps.*formula` patterns
  and returns the new computation_methods record.

WO-C-004 picks option (b) — keeps the base `KnowledgeQuery` untouched
(it is still the production query API in spirit) and adds an experimental
B2-style route. Same boundary disclaimer applies.

## Boundary

`process_calc/` is **a Python module that becomes part of the product
package** — it is not an experiment. The contract above is frozen for
Phase 1; Phase 2+ may add methods but must not change the return shape.

`process_calc.calculate(...)` does not access SQLite, network, or any
external state. It is pure-function arithmetic verifiable in CI.

The agent_query_eval seed integration (WO-C-004) is the only experimental
part of Sprint C — it adds a new candidate-family route to satisfy the
capability evaluator. That is the same B2-style adapter pattern; the
process_calc module itself is independent of it.

## Rollback / Preconditions

Preconditions:

- B1 + B2 already merged on main.
- POC `poc_process_calc.py` available for migration reference.
- `experiments/calculation_ready_extraction/output/` cylinder-liner
  fixtures available for finish-to-grind verification.

Rollback:

- Revert WO-C-001..004 commits.
- POC `poc_process_calc.py` is preserved — Sprint C does not delete it
  (kept as historical reference until Phase 2+ supersedes it).
- No production database, OpenClaw runtime, or external service touched.

## Independent design review

Risks reviewed:

- **Scope creep**: 34-method full implementation is too large for one
  Sprint. Mitigated by Phase 1 = 5 methods only, frozen contract, explicit
  Phase 2 deferral.
- **Tolerance lookup completeness**: ISO 286-1 has many fit classes; Phase 1
  ships H7/h6/g6/H8 + general 0.5-500mm range. Out-of-range diameters raise
  `InputOutOfRangeError` rather than guessing. Mitigated.
- **Public contract drift**: shape is frozen on day 1. Future methods must
  conform.
- **Test brittleness**: textbook example values can be off by formatting
  (mm vs μm). Tests will assert exact integer μm values per ISO 286-1
  to avoid float drift.

Decision: proceed.
