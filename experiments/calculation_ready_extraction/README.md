# Calculation-Ready Extraction POC

This experiment is the Phase 1 execution of:

```text
design/knowledge-db-correctness-v5.md
```

Goal:

```text
source PDF VLM extraction
  -> schema validation
  -> gold comparison
  -> deterministic quality gates
  -> route merge
  -> SQLite prototype
  -> deterministic allowance calculation
```

Input fixtures come from:

```text
experiments/vlm_source_pdf_process_cards/output/vlm_page_106.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_107.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_108.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_109.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_110.json
```

Gold fixture:

```text
experiments/vlm_source_pdf_process_cards/fixtures/gold/p108_cylinder_liner.json
```

Run:

```bash
python3 -m pytest experiments/calculation_ready_extraction/tests -q
python3 experiments/calculation_ready_extraction/scripts/run_poc.py
```

Expected high-level result:

- output shaft route merges to 12 steps
- seal positioning sleeve route merges to 13 steps
- cylinder liner p108 allowance calculation returns `0.8mm` diameter allowance and `0.4mm` single-side allowance
- quality gate detects the known p108 `φ305±0.5` VLM mismatch
- quality gate detects zero-step and missing continuation part-name issues
