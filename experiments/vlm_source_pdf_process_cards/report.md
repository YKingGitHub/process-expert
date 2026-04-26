# Source-PDF VLM Process Card Experiment Report

## Scope

This experiment checks whether the previous POC extraction should be trusted as deterministic-calculation input.

Worktree:

```text
/root/process-expert-calc-test
branch: experiment/process-calc-chain-test
```

Source PDF:

```text
references/工艺知识库.pdf
```

Rendered pages:

- p106: output shaft process card start
- p107: output shaft continuation
- p108: cylinder liner process card
- p109: seal positioning sleeve start
- p110: seal positioning sleeve continuation

Rendered images are under:

```text
experiments/vlm_source_pdf_process_cards/fixtures/page_images/
```

## What Was Added

- source-PDF VLM extraction prompt
- strict JSON schema validator
- VLM runner script for DashScope-compatible image extraction
- manual gold fixture for p108 cylinder liner
- comparison script for manual gold vs previous POC fixture
- tests that prove the previous POC fixture loses symmetric tolerance information

## Key Finding

The previous POC extraction is not reliable enough to serve as ground truth for deterministic calculation.

Manual source-PDF gold for p108 contains:

```text
step 8 inner: φ279.2±0.05mm
step 8 outer: φ300.8±0.05mm
step 9 inner: φ279.2±0.05mm
step 9 outer: φ300.8±0.05mm
```

The previous POC fixture contains:

```text
step 8: φ279.2 +0.05 mm; φ300.8 +0.05 mm
step 9: φ279.2 +0.05 mm; φ300.8 +0.05 mm
```

That loses the lower deviation:

```text
gold: lower_deviation = -0.05
POC:  lower deviation is effectively missing or can be misread as 0
```

This is a calculation-grade error. It affects limit-size calculations, tolerance chains, and allowance verification.

## Local Validation

Validate p108 manual gold:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/validate_process_card_json.py \
  experiments/vlm_source_pdf_process_cards/fixtures/gold/p108_cylinder_liner.json
```

Result:

```text
valid: true
```

Compare manual gold to the previous POC fixture:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/compare_gold_to_poc.py
```

Result:

```text
mismatch_count: 4
code: symmetric_tolerance_lost
```

Run tests:

```bash
python3 -m pytest experiments/vlm_source_pdf_process_cards/tests -q
```

Result:

```text
3 passed in 0.02s
```

Full experiment tests:

```bash
python3 -m pytest \
  experiments/process_calc_extracted_content/tests \
  experiments/vlm_source_pdf_process_cards/tests \
  -q
```

## VLM Call Status

Executed with the Coding Plan API key from:

```text
/opt/ai-stack/compose/.env
```

The script is:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/vlm_extract_process_cards.py \
  --pages 106 107 108 109 110
```

It writes validation-wrapped outputs to:

```text
experiments/vlm_source_pdf_process_cards/output/
```

Actual outputs:

```text
p106 errors=0
p107 errors=0
p108 errors=0
p109 errors=0
p110 errors=0
```

## VLM Extraction Findings

Positive:

- p108 visual extraction preserves `φ279.2 ±0.05` and `φ300.8 ±0.05` correctly.
- p108 output converts them to `upper_deviation=0.05`, `lower_deviation=-0.05`.
- p108 also handles `φ280 +0.08/0`, `φ300 +0.08/+0.04`, and `φ300 +0.04/0`.
- p106 output-shaft page preserves `+0.024/+0.011`, `+0.021/+0.002`, and explicit `留磨削余量 0.8mm`.

Remaining issues:

- p108 step 7 reads `φ305±0.5` as `upper_deviation=0.5`, `lower_deviation=0.0`; source should be symmetric.
- p107 continuation page returns an empty `part_name` for the continuation card and also emits a zero-step `缸套` card because the next section title is visible on the same page.
- p110 continuation page returns an empty `part_name`, so continuation merge still needs deterministic page/table context.
- Some positive deviation source strings are normalized awkwardly, for example `φ90+0.5 +0.2 mm`; numeric fields are usable but source text is not ideal.

Interpretation:

Source-PDF visual extraction is better than the old POC DB for calculation-critical tolerance signs, but it is not self-validating. It still needs:

- source-page gold samples
- schema validation
- continuation merge logic
- numeric consistency checks for symmetric tolerance patterns
- deterministic readiness gating before calculation

## Updated Judgment

The first deterministic-calculation POC should be interpreted narrowly:

```text
If process-card data is correctly structured, Python deterministic calculation is feasible.
```

It should not be interpreted as:

```text
The previous unified_extract.db process-card extraction is accurate enough for calculation.
```

Before expanding deterministic calculation, the extraction input should be rebuilt or verified from source PDF images.

Recommended next gate:

```text
source PDF page image
  -> VLM strict JSON extraction
  -> schema validation
  -> gold sample comparison
  -> deterministic calculation readiness check
```

Only records that pass this gate should be used for Python calculations.
