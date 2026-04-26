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

The first sprint intentionally uses a manual gold seed. This tests the query contract and evaluation harness before replacing records with source-PDF VLM extraction.

Run:

```bash
python3 experiments/agent_query_eval/scripts/evaluate.py
python3 -m pytest experiments/agent_query_eval/tests -q
```

Expected:

- 21 fixed questions: 20 core questions plus 1 out-of-taxonomy question
- intent accuracy >= 90%
- all answered results include citations
- lookup answers include `result_json`
- computation answers include `method_id` or `not_implemented`
- case answers are marked `reference_case`
- out-of-taxonomy questions can return `unknown_query` or `mixed_query` with `candidate_type`
