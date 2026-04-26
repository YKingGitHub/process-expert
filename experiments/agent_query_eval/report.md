# Agent Knowledge Query Precision POC Report

## Scope

Executed Sprint A from:

```text
design/agent-knowledge-query-precision-v1.md
```

Worktree:

```text
/root/process-expert-calc-test
branch: experiment/process-calc-chain-test
```

This sprint does not try to solve full-book extraction. It validates the query contract first:

```text
Agent question
  -> intent classification
  -> correct knowledge family
  -> structured result
  -> source_page + source_text citation
  -> evaluation report
```

## Implemented

### 1. Question Set

Created:

```text
experiments/agent_query_eval/data/questions.json
```

Coverage:

| Group | Count | Purpose |
| --- | ---: | --- |
| P | 5 | principle / process analysis queries |
| L | 5 | lookup / standard parameter queries |
| C | 5 | computation method queries |
| E | 5 | worked example / case queries |
| X | 1 | outside current taxonomy, should return candidate type |

The X question tests the design requirement that the current taxonomy is not fixed:

```text
unknown_query + candidate_type = drawing_requirement_records
```

### 2. Manual Gold Seed

Created:

```text
experiments/agent_query_eval/data/gold_seed.json
```

Seed families:

- `principle_records`
- `lookup_records`
- `computation_methods`
- `case_records`
- `candidate_type_records`

This is intentionally manual for Sprint A. It tests query behavior before replacing records with source-PDF VLM extraction.

### 3. Query API

Implemented:

```text
experiments/agent_query_eval/src/query_api.py
```

Functions:

- `classify_intent(question)`
- `answer_for_agent(question)`
- `search_principles(question)`
- `lookup_parameters(question)`
- `search_computation_methods(question)`
- `search_cases(question)`
- `search_mixed(question)`

Return contract:

```json
{
  "intent": "lookup_query",
  "candidate_type": null,
  "status": "answered",
  "hits": [],
  "citations": [],
  "warnings": []
}
```

### 4. Evaluation Harness

Implemented:

```text
experiments/agent_query_eval/src/evaluator.py
experiments/agent_query_eval/scripts/evaluate.py
```

Checks:

- expected intent
- expected status
- non-empty hits for answered queries
- citations include `source_page` and `source_text`
- lookup hits contain structured `result_json`
- computation hits contain `method_id` and `implementation_status`
- case hits are marked `reference_case`
- outside-taxonomy questions include candidate type or warning

## Results

Command:

```bash
python3 experiments/agent_query_eval/scripts/evaluate.py
```

Result:

```json
{
  "question_count": 21,
  "passed_count": 21,
  "pass_rate": 1.0,
  "intent_accuracy": 1.0,
  "failed": []
}
```

Full report:

```text
experiments/agent_query_eval/output/agent_query_eval_report.json
```

Regression command:

```bash
python3 -m pytest \
  experiments/process_calc_extracted_content/tests \
  experiments/vlm_source_pdf_process_cards/tests \
  experiments/calculation_ready_extraction/tests \
  experiments/agent_query_eval/tests \
  -q
```

Result:

```text
25 passed in 0.12s
```

## What This Proves

Sprint A proves the query evaluation frame is workable:

1. Agent questions can be classified into current query intents.
2. Current four families are enough for the initial 20 core questions.
3. The system can represent an out-of-taxonomy question without forcing it into the wrong family.
4. Query results can be checked for product-relevant contracts, not only text similarity.
5. The result shape can support downstream Agent planning because it returns citations and structured payloads.

## Important Limits

This sprint does not prove:

- the book has been extracted correctly
- all records are source-PDF verified
- lookup values are complete
- all computation methods are implemented
- the taxonomy is final

The seed is manual. That is intentional at this stage.

## Issues / Follow-Ups

1. Some lookup seed records still use placeholder `source_page=0` because the exact original table page was not confirmed in this sprint. Sprint B must replace these with source-PDF extracted records.
2. Current ranking is deterministic keyword scoring with manual boosts. It is acceptable for the harness, but product query should use structured filters first and semantic fallback second.
3. Mixed queries are still shallow. Future work should return a planned query bundle rather than just top hits.
4. Candidate type handling is proven for one case only: `drawing_requirement_records`.

## Next Step

Proceed to Sprint B:

```text
Source PDF Extraction Seed Replacement
```

Recommended first replacement targets:

1. Replace `PR-THIN-WALL-001` from p108 source text.
2. Replace `PR-INSPECTION-KEYSLOT-001` from p107 source text.
3. Replace `LU-ALLOW-GRIND-001` from p108 VLM dimensions/calculation.
4. Replace `CASE-SHAFT-OUTPUT-001`, `CASE-CYLINDER-LINER-001`, `CASE-SEAL-SLEEVE-001` from VLM process-card outputs.

Keep the same 21-question evaluation as the regression gate.
