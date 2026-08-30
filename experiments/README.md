# Experiments Reading Guide

This directory contains the checked-in experiment assets from the knowledge-base correctness and Agent query precision work.

The experiments are intentionally kept outside the production Stage 1-5 workflow. They are reproducible POCs with source-backed fixtures, focused tests, and short reports that explain what each test proved or disproved.

## Why These Experiments Exist

The product goal is:

```text
drawing / part print
  -> Agent identifies required process knowledge
  -> knowledge base returns precise principles, lookup parameters, calculations, and cases
  -> Agent generates a traceable process plan / process card
```

The current phase is not final process-card generation. It tests whether the knowledge base can provide correct, usable information to the Agent.

The main finding is that a usable process knowledge base cannot be only a table-search database. It needs at least these knowledge families:

| Family | Role |
| --- | --- |
| `principle_records` | Process planning principles, datum selection, route logic |
| `lookup_records` | Standard tables, parameters, tolerances, roughness, equipment facts |
| `computation_methods` | Formula-backed methods that should call deterministic Python |
| `case_records` | Worked examples and source process cards |

Additional candidate families are allowed when evidence shows a repeated need, for example `inspection_records`, `standard_clause_records`, `equipment_capability_records`, `feature_process_records`, and `wire_cut_process_records`.

## Recommended Reading Order

1. `vlm_source_pdf_process_cards/`
   - Start here to understand why previous POC extraction is not reliable enough for calculation-grade data.
   - Key report: `vlm_source_pdf_process_cards/report.md`

2. `calculation_ready_extraction/`
   - Shows the guarded path from source-PDF VLM output to quality gates, route merge, SQLite prototype, and allowance calculation.
   - Key report: `calculation_ready_extraction/report.md`

3. `agent_query_eval/`
   - Tests whether Agent questions can retrieve the right family, structured contract, and citation.
   - Key report: `agent_query_eval/report.md`

4. `prose_principle_extraction/`
   - Extracts non-table prose principles, such as keyslot symmetry inspection, which process-card tables do not contain.
   - Key entry: `prose_principle_extraction/README.md`

5. `process_calc_extracted_content/`
   - Earlier deterministic-calculation feasibility test using frozen `unified_extract.db` fixtures.
   - Useful as background, but source-PDF-backed extraction is preferred for calculation-grade truth.

## Directory Map

```text
experiments/
├── agent_query_eval/
│   ├── data/                 # question set, gold seed, source-backed seed
│   ├── src/                  # local query API and evaluator
│   ├── tests/                # pytest contract tests
│   └── report.md             # result summary
│
├── vlm_source_pdf_process_cards/
│   ├── fixtures/gold/        # manual gold for p108 cylinder liner
│   ├── fixtures/page_images/ # rendered source PDF pages p106-p110
│   ├── fixtures/vlm_outputs/ # checked-in VLM JSON outputs used by tests
│   ├── scripts/              # render, validate, compare, VLM extraction
│   ├── tests/                # schema and diff tests
│   └── report.md
│
├── calculation_ready_extraction/
│   ├── src/                  # loader, quality gate, route merge, calculation
│   ├── tests/                # end-to-end deterministic tests
│   └── report.md
│
├── prose_principle_extraction/
│   ├── fixtures/source/      # checked-in prose evidence
│   ├── prompts/
│   ├── scripts/
│   └── tests/
│
└── process_calc_extracted_content/
    ├── fixtures/             # frozen extraction fixtures
    ├── src/                  # route model, parser, calculators
    ├── tests/
    └── report.md
```

## Sample Findings

### 1. Calculation-Grade Extraction Must Use Source Evidence

The old POC fixture lost symmetric tolerance information:

```text
source gold: φ279.2±0.05mm
old POC:     φ279.2 +0.05 mm
```

This changes the lower deviation and can break limit-size, tolerance-chain, and allowance calculations.

### 2. Quality Gate Can Pass With Flags

The source-PDF VLM pipeline is not blindly accepted. It produces flags such as:

```text
continuation_part_missing: p107, p110
zero_step_card: p107 next-section title card
gold_dimension_mismatch: p108 step 7 φ305±0.5 read as +0.5/0
```

That is why downstream code distinguishes `accepted`, `passed_with_flags`, and `needs_human_review`.

### 3. Deterministic Calculation Is Feasible When Inputs Are Good

For the cylinder liner fixture:

```text
inner diameter: 279.2 -> 280.0 = 0.8mm diameter allowance
single-side allowance = 0.4mm

outer diameter: 300.8 -> 300.0 = 0.8mm diameter allowance
single-side allowance = 0.4mm
```

The target architecture is for the Agent to select the method and parameters, while Python performs deterministic validation and calculation.

## Run The Checked-In Tests

The full experiment regression does not require live VLM calls:

```bash
python3 -m pytest experiments/ tests/ -q
```

Live extraction scripts are optional and require `DASHSCOPE_API_KEY`.
