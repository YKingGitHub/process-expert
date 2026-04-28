# Knowledge Capability Evaluation Baseline Report

## Purpose

The real drawing test showed that a single held-out drawing can expose useful
gaps, but the project should not hardcode fixes around that one drawing. This
baseline converts those gaps into reusable capability questions.

## What This Adds

- 7 capability families.
- 21 fixed questions.
- Required annotations for each question:
  - `expected_family`
  - `expected_subtype`
  - `expected_contract`
- A real-drawing gap map that links held-out failures to general capabilities.
- A deterministic report with `gap_count_by_capability`.

## Current Baseline Meaning

The baseline is expected to show both coverage and gaps:

- Covered examples include existing source-backed principles, lookup records,
  computation method contracts, and process-card cases.
- Gaps remain for drawing requirement interpretation, GD&T inspection,
  equipment capability matching, D-shaped/non-round feature process selection,
  blank-to-finished allowance planning, and Python-executable calculations.

This is intentional. The goal is to decide which general capability a future
seed, schema, or `process_calc` implementation improves.

## Commands

```bash
python3 experiments/knowledge_capability_eval/scripts/evaluate.py
python3 -m pytest experiments/knowledge_capability_eval/tests -q
```

