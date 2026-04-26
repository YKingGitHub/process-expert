# Agent Knowledge Query Precision POC

This experiment executes Sprint A from:

```text
design/agent-knowledge-query-precision-v1.md
```

Goal:

```text
Agent question
  -> intent classification
  -> correct knowledge family
  -> structured query result
  -> source_page + source_text citations
  -> evaluation report
```

Sprint A used a manual gold seed to test the query contract. Sprint B adds a source-PDF-backed seed generated from the p106-p110 process-card VLM outputs.

Run:

```bash
python3 experiments/agent_query_eval/scripts/build_source_seed.py
python3 experiments/agent_query_eval/scripts/evaluate.py
python3 experiments/agent_query_eval/scripts/evaluate.py --seed gold
python3 -m pytest experiments/agent_query_eval/tests -q
```

Expected:

- 21 fixed questions: 20 core questions plus 1 out-of-taxonomy question
- default evaluation uses `data/source_replaced_seed.json`
- `data/gold_seed.json` remains as the manual baseline
- intent accuracy >= 90%
- all answered results include citations
- lookup answers include `result_json`
- computation answers include `method_id` or `not_implemented`
- case answers are marked `reference_case`
- out-of-taxonomy questions can return `unknown_query` or `mixed_query` with `candidate_type`

Sprint B source replacement currently covers 10 records:

- 3 principle records
- 3 lookup records
- 1 computation method
- 3 case records

The keyslot symmetry inspection record is intentionally retained as manual seed because the current process-card VLM output does not include the full prose evidence for `偏摆仪及量块`.
