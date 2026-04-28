---
id: D-PROCESS-20260428-01-capability-seed-expansion-b1
title: PROCESS B1 Capability Seed Expansion
status: draft
approved_by_user: false
quality_gate: plan-v1
created: 2026-04-28
workflow_baseline: A18
---

# PROCESS B1 Capability Seed Expansion

## Summary

B1 extends the Sprint A capability baseline with source-backed candidate
knowledge families. The product goal is to prove that selected real-drawing
gaps can be reduced by adding auditable seed records and a deterministic
experiment query adapter.

Current Sprint A baseline:

```text
question_count = 21
capability_count = 7
covered_count = 10
gap_count = 11
```

B1 target:

```text
existing source seed
  + B1 source-backed candidate fixtures
  -> expanded query adapter
  -> knowledge_capability_eval rerun
  -> gap_count_by_capability improves with evidence
```

This remains PROCESS product work inside the independent `process-expert`
repository. It is not an OpenClaw runtime change and does not touch Feishu,
wiki APIs, or production Stage 1-5 behavior.

## Scope

- Add an experimental `capability_seed_expansion` package under
  `experiments/`.
- Add candidate source fixtures for three high-value families:
  `standard_clause_records`, `inspection_records`, and
  `equipment_capability_records`.
- Add a source manifest that records where each candidate record came from.
- Add seed merge helpers that combine the existing source-backed seed with B1
  candidate records.
- Add an `ExpandedKnowledgeQuery` experiment adapter that delegates existing
  four-family questions to the current `KnowledgeQuery` and handles B1
  candidate families deterministically.
- Add an offline evaluation script that compares Sprint A and B1 gap counts.
- Add pytest coverage for fixture contracts, manifest contracts, no-review
  gating, capability gap reduction, and real-drawing gap mapping.
- Keep all live VLM/LLM/API calls out of tests.

## Non-Goals

- Do not generate final process cards.
- Do not modify OpenClaw runtime, tools, Feishu, wiki APIs, or outbound
  notification paths.
- Do not modify production Stage 1-5 search/generation behavior.
- Do not build the full production database schema.
- Do not call live VLM or LLM in tests.
- Do not scrape or commit copyrighted standard text wholesale.
- Do not treat generic RAG metrics as the acceptance gate for engineering facts.
- Do not claim candidate-family records are production schema decisions.

## Contract Context Used

- Product repository `README.md`: experiments are checked-in POCs outside the
  production Stage 1-5 flow; current full regression is `44 passed`.
- `experiments/README.md`: current base families are `principle_records`,
  `lookup_records`, `computation_methods`, and `case_records`; candidate
  families are allowed when repeated needs appear.
- `experiments/agent_query_eval/`: source-backed seed and deterministic
  `KnowledgeQuery` answer contract.
- `experiments/real_drawing_knowledge_planning/`: held-out drawing gaps and
  knowledge package behavior.
- `experiments/knowledge_capability_eval/`: Sprint A baseline and
  `gap_count_by_capability` evaluator.
- Management mirror:
  `Projects/process-expert/design/agent-knowledge-query-precision-v1.md`.
- Weekly report:
  `Projects/process-expert/weekly-report/20260426.md`.
- Workflow style reference:
  `Projects/dev-management/designs/2026-04-27-09-codex-workflow-v3-a18-dependency-aware-execution-queue/design.md`.

## Current Findings

Sprint A already proves that the current source-backed seed can cover route
planning, some machining allowance planning, existing process-card cases, and
some deterministic calculation method contracts.

The same baseline also shows unresolved gaps:

```text
deterministic_calculation: 1
drawing_requirement_interpretation: 3
equipment_operation_capability: 2
feature_process_selection: 2
geometric_tolerance_inspection: 2
machining_allowance_planning: 1
route_planning: 0
```

The highest-value B1 gaps are not the largest count mechanically. They are the
real-drawing blockers that prevent an auditable process plan:

| Candidate family | Reason to do first | Example gaps |
| --- | --- | --- |
| `standard_clause_records` | The real drawing explicitly references `GB/T1804-m`; the Agent must not invent general tolerances. | `DRI-001`, `KN-GENERAL-TOL-001` |
| `inspection_records` | Position tolerance and datum-based inspection are blocking for the held-out drawing. | `GTI-001`, `GTI-003`, `KN-GTOL-POSITION-001` |
| `equipment_capability_records` | The drawing package includes specific equipment; route planning needs machine-operation matching. | `EOC-002`, `EOC-003`, `KN-EQUIPMENT-001` |

Feature-process gaps for D-shaped holes, `2-R4`, milling, and wire cutting are
important but should be B1 stretch or B2 unless strong source evidence is
available immediately. B1 should not fill the baseline with weak manual guesses.

## User And Product Decisions

- The user approves product direction and visible risk; Codex owns the
  technical path, source contract, evaluator correctness, and regression
  evidence.
- B1 should reduce capability gaps, not create a final process-card generator.
- Candidate families can exist in experiments before they become production
  database tables.
- A candidate record only counts as covered when it has source metadata,
  source evidence, and a quality status that is not `needs_human_review`.
- Short source evidence is acceptable; long verbatim standard clauses are not.
- Real drawing gaps guide prioritization, but the question set remains
  capability-level to avoid one-sample overfitting.

## Research Summary

- OpenAI eval guidance recommends defining the objective, collecting a relevant
  dataset, defining metrics, running comparisons, and continuously evaluating
  changes. It also warns against vague "seems to work" evaluation and notes
  that Q&A evals should check context recall/precision and answer usefulness.
  Source: <https://platform.openai.com/docs/guides/evaluation-best-practices>
- LlamaIndex separates response evaluation from retrieval evaluation and
  describes retrieval evaluation as question sets plus ground-truth relevant
  contexts, scored with metrics such as hit rate, precision, and MRR. Source:
  <https://docs.llamaindex.ai/en/stable/module_guides/evaluating/>
- Ragas and DeepEval provide generic RAG metrics such as context precision,
  recall, answer relevancy, and faithfulness. They may be useful later for
  generated answers, but B1 needs deterministic family, contract, and source
  coverage gates first. Sources:
  <https://docs.ragas.io/en/latest/concepts/metrics/index.html> and
  <https://github.com/confident-ai/deepeval/blob/main/docs/guides/guides-rag-evaluation.mdx>

Rejected research option: adding a generic RAG evaluation framework in B1.
The immediate product question is whether source-backed engineering knowledge
exists and is retrievable, so B1 should use fixed JSON fixtures, pytest, and
explicit contract checks.

## Existing System Reuse

| Existing asset | Reuse |
| --- | --- |
| `experiments/agent_query_eval/data/source_replaced_seed.json` | Base seed to expand. |
| `experiments/agent_query_eval/src/query_api.py` | Existing four-family behavior; delegate to it instead of rewriting it. |
| `experiments/knowledge_capability_eval/data/capability_questions.json` | Primary question set and expected contracts. |
| `experiments/knowledge_capability_eval/src/evaluator.py` | Primary gap-count evaluator. |
| `experiments/knowledge_capability_eval/data/real_drawing_gap_map.json` | Real drawing gap mapping. |
| `experiments/real_drawing_knowledge_planning/fixtures/*` | Held-out drawing and equipment context. |
| Existing process-card VLM fixtures | Source evidence for equipment-operation examples where applicable. |

## Target Experiment Contract

B1 creates this directory shape:

```text
experiments/capability_seed_expansion/
├── README.md
├── design.md
├── data/
│   ├── candidate_seed.json
│   └── source_manifest.json
├── src/
│   ├── __init__.py
│   ├── loader.py
│   ├── seed_merge.py
│   └── expanded_query.py
├── scripts/
│   └── evaluate.py
└── tests/
    └── test_capability_seed_expansion.py
```

### Candidate Seed Contract

`candidate_seed.json` stores B1 records grouped by family:

```json
{
  "standard_clause_records": [],
  "inspection_records": [],
  "equipment_capability_records": []
}
```

Every record must include:

```text
id
knowledge_type
family
subtype
topic
source_doc
source_page
source_ref
source_text
quality_status
quality_flags
tags
result_json or method_json or guidance_json
```

Rules:

- `source_text` must be short and auditable.
- `source_ref` identifies the page, table, fixture, or provided input file.
- Allowed `quality_status` values are `accepted`, `accepted_with_flags`, and
  `needs_human_review`.
- `needs_human_review` records may explain gaps but cannot count as covered.

### Source Manifest Contract

`source_manifest.json` records source provenance:

```text
record_id
source_kind
source_path_or_doc
source_page
source_ref
evidence_type
copyright_note
review_status
```

The manifest lets later work replace a weak seed with stronger PDF, VLM, or
reviewed handbook evidence without changing the eval question.

## Query Adapter Contract

B1 must not turn the old `KnowledgeQuery` into a production query engine.
Instead, it adds `ExpandedKnowledgeQuery` under the experiment:

1. Load `source_replaced_seed.json`.
2. Load `candidate_seed.json`.
3. Merge them into an expanded seed.
4. Delegate existing four-family questions to `KnowledgeQuery`.
5. Handle B1 candidate families with deterministic matching.
6. Return the same answer shape:

```text
intent
status
hits
citations
warnings
```

The adapter is experimental and deterministic. It exists to make capability
coverage measurable, not to define final production retrieval behavior.

## Evaluation Contract

`capability_seed_expansion/scripts/evaluate.py` must produce a local JSON report
with at least:

```text
baseline_gap_count
expanded_gap_count
gap_delta_by_capability
real_drawing_mapped_gap_covered_count
candidate_records_by_family
records_blocked_by_quality_status
```

Target thresholds:

```text
baseline_gap_count = 11
expanded_gap_count <= 8
real_drawing_mapped_gap_covered_count >= 2
```

The absolute number is less important than the auditable reason each gap moved
from uncovered to covered.

## Automation And Interrupt Policy

```yaml
automation:
  on_design_approval: run_all_work_orders
  known_high_risk_actions_preapproved_by_design: []
  auto_repair_soft_issues: true
  max_repair_attempts_per_wo: 2
  report_soft_issues_in_evidence: true
  interrupt_only_on:
    - implementation_scope_differs_from_approved_design
    - required_source_evidence_missing
    - copyrighted_standard_text_would_be_copied_at_length
    - candidate_record_without_source_manifest
    - needs_human_review_record_required_to_pass_acceptance
    - live_api_key_or_vlm_call_required_for_tests
    - production_stage_or_openclaw_runtime_change_requested
    - secret_or_private_data_risk
    - destructive_operation_not_declared_in_design
```

## Alternatives

- Add Ragas, DeepEval, or another generic RAG framework now.
- Modify production Stage 3 search directly.
- Expand all 11 gaps at once.
- Edit only `KnowledgeQuery` and skip a separate expanded adapter.
- Treat all candidate records as covered.
- Start with feature-process gaps for D-shaped holes and wire cutting.

## Rejected Options

- Generic RAG frameworks are rejected for B1 because the gate is
  source/family/contract coverage, not generated answer quality.
- Direct production search changes are rejected because candidate families have
  not yet proven value in experiments.
- Expanding all 11 gaps is rejected because it encourages weak manual filler
  records.
- Editing only `KnowledgeQuery` is rejected because it hides candidate-family
  behavior inside the older POC and makes comparison harder.
- Treating all candidate records as covered is rejected because source and
  quality contracts must decide coverage.
- Starting with D-shaped holes and wire cutting is deferred unless strong
  source evidence is immediately available.

## Acceptance

- B1 adds source-backed candidate fixtures for at least
  `standard_clause_records`, `inspection_records`, and
  `equipment_capability_records`.
- Every B1 record has source metadata, source evidence, and a source manifest
  entry.
- No `needs_human_review` record counts as covered in the capability score.
- The B1 evaluator reports `expanded_gap_count <= 8`.
- At least 2 real-drawing mapped gaps become covered.
- Existing experiment regression still passes after adding B1 tests.
- Tests run offline without `DASHSCOPE_API_KEY` or live VLM/LLM calls.
- B1 docs explain that the query adapter is experimental, not production
  retrieval.

## Rollback / Preconditions

Preconditions:

- Sprint A baseline commit exists in the current branch.
- Source evidence for at least two blocking real-drawing gaps is available and
  safe to commit as short fixtures.
- The team confirms whether `standard_clause_records` may use paraphrased
  structured values with source metadata, or whether a checked-in source
  excerpt will be provided.
- The main PROCESS worktree is not required; work continues in the independent
  B1 worktree.

Rollback:

- Delete `experiments/capability_seed_expansion/`.
- Revert README or regression-command updates introduced by B1.
- No production database, OpenClaw runtime state, Feishu config, or external
  service state is touched.

## Work Orders

| Work Order | Name | Purpose | Depends On |
| --- | --- | --- | --- |
| WO-B1-001 | Fixture Contract And Seed Merge | Create `candidate_seed.json`, `source_manifest.json`, loaders, and seed merge helpers; reject missing source metadata and long unreviewed source text. | Sprint A baseline |
| WO-B1-002 | Expanded Query Adapter | Implement `ExpandedKnowledgeQuery` for B1 candidate families while preserving existing `KnowledgeQuery` behavior. | WO-B1-001 |
| WO-B1-003 | Capability Evaluation Integration | Add the B1 evaluation script and comparison summary for baseline vs expanded gap counts. | WO-B1-002 |
| WO-B1-004 | Docs And Regression | Update experiment docs and root regression command if test count changes; run full regression and record B1 summary. | WO-B1-003 |

## Independent Design Review

Review result: acceptable with constraints.

- The design is correctly scoped as experiment-level PROCESS work and does not
  mix in OpenClaw runtime concerns.
- The strongest decision is to reduce a small number of real blocking gaps with
  auditable source fixtures instead of filling all 11 gaps with weak data.
- The main risk is source quality: B1 must not count manually invented records
  as covered. The source manifest and `needs_human_review` gate mitigate this.
- The second risk is copyright-sensitive standard content. B1 mitigates this by
  requiring short evidence and structured/paraphrased values rather than long
  copied clauses.
- The third risk is confusing the experiment adapter with production retrieval.
  Keeping the adapter inside `experiments/` and documenting its boundary is
  sufficient for B1.
