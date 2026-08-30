# Calculation-Ready Extraction POC Report

## Scope

Executed the Phase 1 design test from:

```text
design/knowledge-db-correctness-v5.md
```

Worktree:

```text
<PROJECT_ROOT>-calc-test
branch: experiment/process-calc-chain-test
```

Input:

```text
experiments/vlm_source_pdf_process_cards/output/vlm_page_106.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_107.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_108.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_109.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_110.json
```

Gold:

```text
experiments/vlm_source_pdf_process_cards/fixtures/gold/p108_cylinder_liner.json
```

## Implemented

### 1. Calculation-Ready Quality Gate

Implemented:

- schema validation handoff
- zero-step card detection
- missing continuation part-name detection
- deterministic tolerance sign check
- manual gold comparison for p108

Detected expected flags:

```text
continuation_part_missing: p107, p110
zero_step_card: p107 next-section title card
gold_dimension_missing: p108 casting dimensions omitted by VLM
gold_dimension_mismatch: p108 step 7 φ305±0.5 read as +0.5/0
gold_dimension_mismatch: p108 step 11 duplicate φ300 target matched the wrong gold row
```

The status is intentionally:

```text
passed_with_flags
```

This means the pipeline ran, but the data is not blindly accepted.

### 2. Route Merge

Merged VLM page outputs into process routes:

| Route | Pages | Steps | Status |
| --- | --- | ---: | --- |
| 输出轴 | 106-107 | 12 | accepted |
| 缸套 | 108 | 13 | needs_human_review |
| 密封件定位套 | 109-110 | 13 | accepted |

The cylinder liner route is marked `needs_human_review` because the gold comparison caught calculation-grade extraction issues, even though the specific finish-to-grind allowance fields are usable for smoke calculation.

### 3. SQLite Prototype

Built:

```text
experiments/calculation_ready_extraction/output/calculation_ready_poc.db
```

Counts:

| Table | Count |
| --- | ---: |
| process_routes | 3 |
| process_steps | 38 |
| process_dimensions | 64 |
| process_allowances | 9 |

### 4. AI-Facing Query Prototype

Implemented a minimal query layer:

- `get_process_route(db_path, part_name)`
- `get_step_dimensions(db_path, part_name, step_no)`

Verified:

- query `输出轴` returns 12 ordered steps
- query `缸套` step 8 returns `φ279.2 ±0.05` with `upper=0.05`, `lower=-0.05`

### 5. Deterministic Calculation from VLM JSON

Calculated cylinder liner finish-to-grind allowance from VLM JSON, not old POC DB:

```text
inner: φ279.2 ±0.05 -> φ280 +0.08/0
diameter allowance = 0.8mm
single-side allowance = 0.4mm

outer: φ300.8 ±0.05 -> φ300 +0.08/+0.04
diameter allowance = 0.8mm
single-side allowance = 0.4mm
```

## Test Result

Command:

```bash
python3 -m pytest \
  experiments/process_calc_extracted_content/tests \
  experiments/vlm_source_pdf_process_cards/tests \
  experiments/calculation_ready_extraction/tests \
  -q
```

Result:

```text
18 passed in 0.10s
```

POC runner:

```bash
python3 experiments/calculation_ready_extraction/scripts/run_poc.py
```

Result summary:

```json
{
  "quality_status": "passed_with_flags",
  "quality_flag_count": 8,
  "routes": {
    "输出轴": 12,
    "缸套": 13,
    "密封件定位套": 13
  },
  "db_counts": {
    "process_routes": 3,
    "process_steps": 38,
    "process_dimensions": 64,
    "process_allowances": 9
  }
}
```

Full JSON report:

```text
experiments/calculation_ready_extraction/output/calculation_ready_report.json
```

## Judgment

The design direction is validated for the p106-p110 slice:

```text
source PDF VLM extraction
  -> quality gate
  -> route merge
  -> normalized SQLite
  -> AI-facing query
  -> deterministic calculation
```

The important result is not just that the calculation works. The stronger result is that the gate catches known extraction problems before they are silently trusted.

## Issues Found

1. VLM still misses some dimensions, such as p108 step 1 casting dimensions.
2. VLM can still misread symmetric tolerance, such as p108 step 7 `φ305±0.5`.
3. Mixed pages need filtering: p107 includes a zero-step next-section card.
4. Continuation pages often have empty `part_name`, so route merge must use step sequence and page context.
5. Gold matching needs feature-level disambiguation for repeated same-nominal dimensions, such as p108 step 11 two `φ300` dimensions.

## Next Step

Move from experiment to product-facing implementation in a new sprint:

1. Add `calculation_ready_extraction` logic into product repo under `ingest_v2/` or `ingest/process_cards_v2/`.
2. Promote the current SQLite prototype schema into a versioned DB builder.
3. Expand gold from p108-only to p106-p110 complete gold.
4. Add feature identifiers so repeated dimensions can be matched correctly.
5. Run Ch3 process-card pages with the same gate and report accepted/review/rejected ratios.
