# Deterministic Calculation POC Report

## Scope

This report covers the first implementation pass in the isolated worktree:

```text
/root/process-expert-calc-test
branch: experiment/process-calc-chain-test
```

The POC uses frozen fixtures exported from:

```text
/root/process-expert/output/unified_extract.db
```

No workflow code, `ingest/`, or active `main` worktree files were modified.

## Implemented

### Phase 0: Fixture Freeze

Generated fixtures:

- `fixtures/process_cards_sample.json`: 153 process-card rows
- `fixtures/computation_methods_sample.json`: 34 computation-method rows
- `fixtures/expected_cases.json`: expected route cases for output shaft and seal positioning sleeve

The fixtures let tests run without querying the live DB.

### Phase 1: Route Reconstruction

Implemented:

- `ProcessStep`
- `ProcessRoute`
- operation category normalization
- continuation page merge
- sequence validation with machine-readable warnings

Confirmed cases:

- `输出轴` + `轴类零件（续）` merge into one route with steps 1-12.
- `密封件定位套` + `工序表 (续)` merge into one route with steps 1-13.

One real extraction issue surfaced:

- `轴承座` has a `技术要求` row with `step_no = null`. It is not a process-route step, so route reconstruction skips null `step_no` records. Later it should probably map to a technical-requirement model instead of `process_card_records`.

### Phase 2: Conservative Operation Parser

Implemented parsing for explicit values only:

- diameters: `φ270 ±1 mm`, `φ300 +0.08/+0.04 mm`, `φ279.2 +0.05 mm`
- lengths: `总长 508mm`, `保证工件总长 500.4mm`
- allowances: `留磨削余量 0.8mm`, `留加工余量 5 ~ 6mm`, `留磨量 0.8mm`
- rough surface inference from nearby text: `inner`, `outer`, or `unknown`

The parser preserves the source substring and does not invent missing values.

### Phase 3: Process-Chain Calculation

Implemented two calculation checks:

1. `analyze_cylinder_liner_allowance(route)`
   - parses the `缸套` process chain
   - confirms inner diameter is non-decreasing
   - confirms outer diameter is non-increasing
   - computes finish-to-grind diameter allowance:
     - inner: `279.2 -> 280.0 = 0.8mm`, single-side `0.4mm`
     - outer: `300.8 -> 300.0 = 0.8mm`, single-side `0.4mm`

2. `analyze_explicit_grinding_allowance(route)`
   - parses explicit output-shaft grinding allowance mentions
   - finds two `0.8mm` grinding allowances
   - links them to later grinding steps 7 and 8
   - returns `needs_more_structured_final_dimension` instead of claiming a numeric pass

This gives both a positive feasibility case and a guarded incomplete case.

## Test Result

Command:

```bash
python3 -m pytest experiments/process_calc_extracted_content/tests -q
```

Result:

```text
10 passed in 0.04s
```

## Current Judgment

Python deterministic calculation is feasible for extracted process-chain content when:

- process-card rows have stable `step_no`
- continuation pages can be detected
- dimensions are explicitly present in operation text
- the check is limited to well-defined local calculations

The strongest current example is `缸套`, where the extracted route supports a real allowance calculation without LLM involvement.

The current boundary is also clear: output-shaft text contains explicit allowance, but final pre/post-grinding dimensions are not structured enough to independently verify the numeric delta. The POC correctly reports that as incomplete.

## Next Step

Phase 4 should add computation-method smoke tests:

- implement a minimal `calculate(method_id, **params)` for selected numeric examples
- start with `calculate_finishing_allowance`, `calculate_pre_plating_dimensions`, `calculate_parallelism_error`, `calculate_perpendicularity_error_seam_gauge`, and `calculate_hardening_degree`
- keep all unverified or non-numeric example methods marked as incomplete rather than passed

After that, the useful product-facing direction is a narrow module:

```text
extracted process cards
  -> route reconstruction
  -> conservative numeric parser
  -> deterministic validators/calculators
  -> structured result with steps and warnings
```
