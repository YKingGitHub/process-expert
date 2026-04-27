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

Sprint A is complete.

## Sprint B Update

Implemented:

```text
experiments/agent_query_eval/src/source_seed_builder.py
experiments/agent_query_eval/scripts/build_source_seed.py
experiments/agent_query_eval/data/source_replaced_seed.json
experiments/agent_query_eval/data/source_replacement_report.json
experiments/prose_principle_extraction/fixtures/source/p107_principles.json
experiments/prose_principle_extraction/scripts/vlm_extract_principles.py
```

The builder uses process-card VLM outputs:

```text
experiments/vlm_source_pdf_process_cards/output/vlm_page_106.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_107.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_108.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_109.json
experiments/vlm_source_pdf_process_cards/output/vlm_page_110.json
```

It also uses the p107 prose-principle fixture:

```text
experiments/prose_principle_extraction/fixtures/source/p107_principles.json
```

Prose fixtures are now loaded directory-wide from:

```text
experiments/prose_principle_extraction/fixtures/source/
```

The quality gate checks schema validity, duplicate record ids, confidence, and whether `source_text` contains actual Chinese source evidence.

It merges process-card pages into three source-backed cases:

| Case | Pages | Steps | Status |
| --- | ---: | ---: | --- |
| 输出轴 | 106-107 | 12 | accepted |
| 缸套 | 108 | 13 | needs_human_review |
| 密封件定位套 | 109-110 | 13 | accepted |

Source replacement result:

| Group | Replaced |
| --- | ---: |
| principle_records | 4 |
| lookup_records | 3 |
| computation_methods | 1 |
| case_records | 3 |
| total | 11 |

The p107 prose fixture replaced:

```text
PR-INSPECTION-KEYSLOT-001
```

Evidence:

```text
图样中键槽未标注对称度要求，但在实际加工中应保证±0.025mm的对称度。
这样便于与齿轮的装配，键槽对称度的检查，可采用偏摆仪及量块配合完成，
也可采用专用对称度检具进行检查。
```

There are now no manual retained records in the source-replaced seed. The important distinction remains: process-card evidence and prose evidence are extracted by different tools and tagged with different `extraction_source.kind` values.

Sprint B evaluation:

```bash
python3 experiments/agent_query_eval/scripts/build_source_seed.py
python3 experiments/agent_query_eval/scripts/evaluate.py
python3 experiments/agent_query_eval/scripts/evaluate.py --seed gold
python3 -m pytest experiments/agent_query_eval/tests -q
```

Results:

```text
source seed: 21/21 passed, intent_accuracy 1.0
gold seed:   21/21 passed, intent_accuracy 1.0
focused tests: 14 passed
full tests:    32 passed
```

The evaluation reports are written separately:

```text
experiments/agent_query_eval/output/agent_query_eval_report_source.json
experiments/agent_query_eval/output/agent_query_eval_report_gold.json
```

Important quality finding:

```text
source_quality.status = passed_with_flags
source_quality.flag_count = 8
prose_quality.status = accepted
prose_quality.fixture_count = 1
prose_quality.record_count = 2
```

The flags are inherited from the existing source-PDF VLM validation, including p108 dimension mismatches. Therefore the cylinder-liner case is query-usable but marked `needs_human_review`; downstream Agent logic should not treat it as fully accepted calculation evidence without checking quality flags.

## Next Step

Proceed to the remaining Sprint B extractor gap:

```text
Scale full-page principle/prose extraction beyond p107
```

Recommended targets:

1. Extract prose around baseline-first / datum-first route principles.
2. Extract thin-wall prose paragraphs, not only process-card-inferred principles.
3. Add a quality gate that requires principle records to cite actual prose when the source claim is not directly represented by table rows.
4. Keep the same 21-question evaluation as the regression gate.

Keep the same 21-question evaluation as the regression gate.
