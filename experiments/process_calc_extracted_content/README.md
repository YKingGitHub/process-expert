# Python Deterministic Calculation Feasibility Test Plan

## Purpose

Validate whether extracted knowledge can support deterministic Python calculation, not only LLM-style retrieval.

The first target is process-chain content from `process_card_records`, because it is already structured enough to test real engineering workflows:

- reconstruct a route from extracted process-card rows
- normalize operation names and continuation pages
- parse dimensions, tolerances, and machining allowances from operation text
- run deterministic checks/calculations on the extracted route

Formula records from `computation_methods` are used as the second target, because they already contain explicit inputs, formulas, outputs, and some examples.

## Constraints

- Work in this independent worktree: `/root/process-expert-calc-test`
- Do not modify `/root/process-expert` main worktree or workflow code.
- Do not touch `ingest/` or current Stage 1-5 workflow modules in this POC.
- No LLM calls in test execution. LLM/VLM extraction is treated as an upstream frozen input.
- Use pure Python standard library for the deterministic layer unless a later implementation proves a real need.

## Source Data

Primary source:

```bash
/root/process-expert/output/unified_extract.db
```

Current profile from that DB:

| Table | Count | Role in Test |
| --- | ---: | --- |
| `process_card_records` | 153 | Main process-chain feasibility target |
| `computation_methods` | 34 | Formula/calculation feasibility target |
| `lookup_records` | 925 | Optional lookup inputs and symbol dictionaries |
| `knowledge_records` | 148 | Optional rule text, not used in deterministic v0 |

Before implementation, freeze a snapshot or export JSON fixtures into this experiment directory so future test results are comparable.

Recommended fixture layout:

```text
experiments/process_calc_extracted_content/
├── README.md
├── fixtures/
│   ├── process_cards_sample.json
│   ├── computation_methods_sample.json
│   └── expected_cases.json
├── src/
│   ├── route_model.py
│   ├── operation_parser.py
│   └── calculators.py
└── tests/
    ├── test_route_reconstruction.py
    ├── test_operation_parser.py
    ├── test_process_chain_calculation.py
    └── test_computation_methods_contract.py
```

## Core Hypotheses

### H1: Process chains can be reconstructed deterministically

Given rows from `process_card_records`, Python can group them into stable process routes with ordered steps.

Signals:

- `step_no` is monotonic after grouping continuation pages.
- each route has a start/end lifecycle such as blanking/casting/forging -> machining -> inspection -> storage.
- route grouping detects continuation pages instead of treating them as unrelated parts.

Expected early issue:

Current extraction sometimes stores continuation rows as separate parts, for example `输出轴` and `轴类零件（续）`. The test should expose this and define a deterministic merge rule.

### H2: Operation semantics can be normalized deterministically

Common operation names can be mapped to canonical categories without LLM:

| Raw examples | Canonical category |
| --- | --- |
| `下料`, `铸`, `铸造`, `锻`, `锻造` | `blank_preparation` |
| `粗车`, `车`, `粗铣`, `铣`, `钻`, `镗` | `rough_or_general_machining` |
| `精车`, `精镗`, `磨`, `粗磨` | `finish_machining` |
| `热处理`, `清砂`, `清理`, `涂漆`, `涂装` | `treatment_or_auxiliary` |
| `检`, `检验`, `探伤` | `inspection` |
| `入库` | `storage` |

This tests whether the extracted `operation_name` field is clean enough for deterministic workflow checks and route analytics.

### H3: Dimensions and allowances are partially calculable from extracted operation text

Many useful values are still embedded in `operation_content`, but a conservative parser should extract enough for a feasibility answer.

Patterns to test:

- diameters: `φ279.2`, `φ300 +0.08/+0.04 mm`
- lengths: `总长 500mm`, `35mm`, `78mm`
- symmetric tolerances: `±0.5 mm`
- upper/lower deviations: `+0.024/+0.011 mm`, `0/-0.043`
- explicit allowances: `留磨削余量 0.8mm`, `留加工余量 5mm`, `各部留加工余量 7mm`
- ranges: `5 ~ 6mm`, `28 ~ 32HRC`

The parser should return structured values with confidence/source spans, not just floats.

### H4: Useful deterministic calculations can run before full extraction perfection

The POC should prove at least three useful calculations:

1. Route health check: missing steps, duplicate steps, invalid continuation grouping, missing equipment for machining operations.
2. Allowance consistency: compare explicit reserved allowance against later process dimensions where both are present.
3. Formula contract: call selected `computation_methods` examples through deterministic functions and verify outputs.

## Test Cases

### Case A: Output shaft route reconstruction

Source rows:

- `输出轴`, `表 3-89`, page 106, steps 1-9
- `轴类零件（续）`, `表3-89（续）`, page 107, steps 10-12

Expected:

- one merged route with 12 steps
- sequence is continuous: 1..12
- categories include blank preparation, heat treatment, turning, finish turning, grinding, milling, inspection, storage
- continuation merge is explicitly recorded in `warnings`

Why this matters:

It tests whether extracted process-card fragments can become one deterministic process chain.

### Case B: Cylinder liner dimension and allowance chain

Source rows:

- `缸套`, `表 3-90`, page 108

Useful extracted values:

- rough turning: inner `φ270 ±1`, outer `φ310 ±1`
- later rough turning: inner `φ275 ±0.5`, outer `φ305 ±0.5`
- finish turning: inner `φ279.2 +0.05`, outer `φ300.8 +0.05`
- grinding: inner `φ280 +0.08/0`, outer `φ300 +0.08/+0.04`

Expected deterministic checks:

- inner diameter increases across operations.
- outer diameter decreases across operations.
- finish-to-grind diameter allowance is `0.8mm` on diameter, `0.4mm` single-side, for both inner and outer surfaces.
- total length decreases from 508 -> 506 -> 504 -> 502 -> 500.8 -> 500.4 -> 500 where extractable.

Why this matters:

It proves process-card text can feed real numeric chain checks even before a dedicated schema exists for every dimension.

### Case C: Output shaft explicit grinding allowance

Source rows:

- `输出轴`, steps 5-8

Useful extracted values:

- step 5: `φ60 ...`, `φ80 ...` each reserves grinding allowance `0.8mm`
- step 6: `φ54.4 ...`, `φ60 ...` reserves grinding allowance `0.8mm`
- steps 7-8: grinding reaches drawing requirements

Expected deterministic checks:

- parser extracts explicit `0.8mm` allowance from steps 5 and 6.
- route links reserved grinding allowance to following grinding steps.
- if final dimensions are not explicit enough to verify delta, the result should be `check_status = "needs_more_structured_final_dimension"`, not a false pass.

Why this matters:

It separates calculable cases from cases requiring better extraction.

### Case D: Seal positioning sleeve rough allowance

Source rows:

- `密封件定位套`, pages 109-110

Useful extracted values:

- casting allowance `7mm`
- rough-turning allowance `5mm`
- finish/rollover page contains grind allowance `0.8mm`

Expected deterministic checks:

- parser extracts all explicit allowance mentions.
- continuation page is grouped with the same part.
- operation categories identify casting -> rough turning -> finish turning -> grinding -> inspection/storage.

### Case E: Computation methods contract smoke test

Source rows:

- `computation_methods`, especially records with concrete numeric `example_json`

Minimum smoke methods:

- `calculate_process_tolerance_distribution`
- `recalculate_tolerance_chain_three_components`
- `calculate_process_dimensions_and_tolerances`
- `calculate_process_dimension_with_intermediate_datum`
- `calculate_pre_plating_dimensions`
- `calculate_finishing_allowance`
- `calculate_parallelism_error`
- `calculate_perpendicularity_error_seam_gauge`
- `calculate_hardening_degree`

Expected:

- deterministic functions return `{result, unit, steps, formula, warnings}`
- numeric examples pass with tolerance `0.001mm` or `0.1%`, whichever is wider
- methods without real numeric examples are marked `verified = false`

## Implementation Phases

### Phase 0: Data freeze and profiling

Deliverables:

- JSON export of selected process-card rows and computation-method rows.
- small profile report: route count, continuation candidates, operation-name frequency, rows with numeric tokens, rows with allowance terms.

Acceptance:

- test fixture can run without querying the live DB.
- profile numbers match the frozen fixture.

### Phase 1: Route reconstruction

Implement:

- `ProcessStep`
- `ProcessRoute`
- grouping by `part_name` + `table_ref`
- continuation detection using table refs like `续`, adjacent pages, and continuous `step_no`
- operation category normalization

Acceptance:

- Case A and Case D reconstruct a single route across continuation pages.
- sequence gaps and duplicates are reported as warnings.

### Phase 2: Conservative operation parser

Implement:

- regex parser for diameter, length, tolerances, explicit allowances, hardness ranges, and equipment presence.
- source-span retention: each parsed value should preserve the substring it came from.
- confidence levels: `explicit`, `derived`, `ambiguous`.

Acceptance:

- fixtures parse expected values for Cases B-D.
- parser never silently invents values.
- ambiguous values are surfaced with warnings.

### Phase 3: Process-chain deterministic calculations

Implement:

- route health calculation
- diameter progression check for inner/outer surfaces
- single-side allowance derivation from diameter deltas
- explicit allowance to later-operation linking

Acceptance:

- Case B computes finish-to-grind single-side allowance `0.4mm`.
- Case C returns a guarded incomplete status instead of claiming verified consistency.
- all calculations return structured result plus steps and warnings.

### Phase 4: Computation-method smoke layer

Implement:

- minimal `calculate(method_id, **params)` prototype for the smoke methods only, or reuse `process_calc` if it exists by then.
- verified/unverified marker.
- contract tests for return shape and numeric tolerance.

Acceptance:

- all selected numeric examples pass.
- unimplemented methods are counted explicitly and do not appear as passed.

## Metrics

### Data readiness metrics

| Metric | Target for POC |
| --- | ---: |
| route reconstruction pass rate on selected cases | 100% |
| continuation routes detected correctly | 100% on selected cases |
| operation category coverage | >= 90% of selected rows |
| rows with numeric mentions parsed into at least one structured value | >= 80% of selected numeric rows |
| parser false invention rate | 0 |

### Calculation metrics

| Metric | Target for POC |
| --- | ---: |
| Case B numeric checks passed | all required checks |
| Case C guarded incomplete result | yes |
| computation method numeric examples | tolerance pass |
| every calculation has steps | 100% |
| every warning condition is machine-readable | 100% |

## Go / No-Go Decision

### Go

Proceed toward a real deterministic calculation module if:

- process routes can be reconstructed from extracted records with deterministic rules.
- at least one real process-card case produces a meaningful numeric allowance calculation.
- guarded incomplete cases are distinguishable from successful calculations.
- formula examples pass without LLM involvement.

### No-Go / Redesign Extraction

Do not expand Python calculation yet if:

- continuation pages cannot be merged reliably from current fields.
- numeric parsing depends on brittle one-off patterns for every part.
- most allowance checks need values that extraction did not preserve.
- route rows lack stable step numbers or operation names.

## Expected Architectural Outcome

If the POC passes, add a narrow deterministic layer beside the workflow, not inside it:

```text
extracted DB / fixtures
  -> process_chain model
  -> deterministic parsers
  -> calculators
  -> structured result with steps/warnings
```

Later workflow integration can be a separate step:

```text
Stage 4 route generation
  -> optional deterministic validator/calculator
  -> route answer with calculated evidence
```

This keeps the POC independent from the active workflow redesign while testing the core question: whether extracted process knowledge can become executable engineering logic.
