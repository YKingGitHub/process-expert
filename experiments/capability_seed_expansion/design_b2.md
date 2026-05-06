---
id: D-PROCESS-20260506-01-capability-seed-expansion-b2
title: PROCESS B2 Capability Seed Expansion — feature/milling/allowance/welding
status: approved
approved_by_user: true
approved_date: 2026-05-06
quality_gate: plan-v1
created: 2026-05-06
workflow_baseline: A18
follows: D-PROCESS-20260428-01-capability-seed-expansion-b1
---

# PROCESS B2 Capability Seed Expansion

## Summary

B2 extends the B1 candidate-family experiment with four more source-backed
families. After B1 the capability gap stands at 6/21; B2 targets reducing it
to ≤ 2 by adding records for the remaining capability questions whose required
families are not yet implemented and whose source evidence is now available.

Lives in the same directory as B1 (`experiments/capability_seed_expansion/`),
extends the same `candidate_seed.json`, `expanded_query.py`, and
`expanded_evaluator.py`. No new top-level experiment.

## Scope

Add records and routing for four candidate families:

| Family | Question coverage | Real-drawing gap coverage | Primary source |
|---|---|---|---|
| `machining_allowance_records` | MAP-003 | KN-BLANK-ALLOWANCE-001 | existing `vlm_source_pdf_process_cards/output/vlm_page_106..110.json` (缸套/输出轴/密封件定位套 finish-to-grind allowance) + `工艺知识库.pdf` Ch3 余量 paraphrase |
| `feature_process_records` | FPS-001 | KN-MILL-D-SHAPE-001 | `金属切削工艺技术手册.pdf` Ch6 铣削 + general feature-process practice paraphrase |
| `milling_process_records` | FPS-002 | (shared with above) | `金属切削工艺技术手册.pdf` Ch6 铣削 |
| `drawing_requirement_records` | DRI-002, DRI-003 | — | `GB/T 324-2008 焊缝符号表示法.pdf` (table 1: 20 basic symbols, table 2: 5 combinations, §4.3 supplementary symbols) |

Out-of-scope (deferred):

- `wire_cut_process_records` (KN-WIRECUT-001): needs additional source
  PDF; left for B3.
- DCA-003 (`python_executable_tolerance_lookup`): needs Sprint C
  `process_calc.calculate()` implementation, not a seed problem.
- DRAWING-QUALITY-D-SHAPE: drawing parser quality gate, Sprint D scope.

## Acceptance gates

```text
baseline_gap_count                    = 11   (Sprint A baseline, unchanged)
b1_gap_count                          = 6    (post-B1)
b2_gap_count                          <= 2   (target after B2)
real_drawing_mapped_gap_covered_count >= 5   (target, was 3 after B1)
no_baseline_covered_question_regresses
no_needs_human_review_record_counted_as_covered
full_regression                       passes
```

The numeric target `≤ 2` corresponds to:

- Best case 0 if all 5 questions (DRI-002 + DRI-003 + FPS-001 + FPS-002 + MAP-003)
  are recovered. DCA-003 stays uncovered (Sprint C) so floor is 1.
- Realistic 1-2 because DRI-002 (待焊面要求) leans on welding practice
  rather than direct GB/T 324 clause; we may end up at `accepted_with_flags`
  but still covering the contract.

## Records (estimated)

```text
machining_allowance_records:    4 records
  + 1 per cylinder/shaft/sleeve case finish-to-grind from existing fixtures
  + 1 generic blank-to-finished rule (KN-BLANK-ALLOWANCE-001)

feature_process_records:        2 records
  + 1 D-shape hole feature → milling on 3-axis MC (FPS-001)
  + 1 generic non-circular internal contour feature

milling_process_records:        3 records
  + 1 inner radius R<= R_tool milling (FPS-002, R4)
  + 1 internal contour milling
  + 1 plane / pocket milling

drawing_requirement_records:    3 records
  + 1 GB/T 324 symbol catalog (table 1 + table 2 + supplementary, lookup-style)
  + 1 weld surface requirement (DRI-002 待焊面 paraphrase)
  + 1 weld symbol callout interpretation guidance (DRI-003)
```

Total ~12 new records. Combined with B1's 33, expanded seed will hold ~45
candidate records.

## Quality status policy

- Each record must include `source_doc`, `source_page`, `source_ref`,
  `source_text` (≤ 240 chars), `quality_status`, `quality_flags`, plus one
  payload (`result_json` / `guidance_json`).
- Allowed statuses: `accepted` (direct standard quote / structured table),
  `accepted_with_flags` (paraphrased general practice with explicit flag).
- `needs_human_review` records may exist for context but must not be relied on
  for capability coverage (consistent with B1).

## Contract checks (new in expanded_evaluator)

| Contract name | What it checks | Used by |
|---|---|---|
| `allowance_planning_contract` | top hit has `result_json` with `step_pair` (predecessor/successor) and `single_side_allowance_mm`; citations present | MAP-003 |
| `feature_to_process_contract` | top hit has `result_json` with `feature_kind` and `recommended_processes` (list); citations present | FPS-001 |
| (extend existing `feature_to_process_contract` for milling subtype) | — | FPS-002 |
| `drawing_requirement_interpretation` | top hit has `guidance_json` with `interpretation` and `applies_to`; citations present | DRI-002, DRI-003 |

`feature_to_process_contract` already exists in the question set (FPS-001 +
FPS-002 declare it). The current base evaluator returns
`contract_not_implemented_in_current_baseline`. B2 implements it.

## Routing rules (new in ExpandedKnowledgeQuery)

```text
machining_allowance_records:
  trigger: "余量" or ("毛坯" and ("外圆" or "外径")) or ("精车" and "磨")
  exclude: questions already routed to lookup_records (MAP-001)

feature_process_records:
  trigger: ("D 型" or "D型" or "异形" or "非圆" or "盲孔") and ("加工" or "工序")
  must include feature signal (specific feature kind)

milling_process_records:
  trigger: ("铣" or "铣削") and ("R" or "圆角" or "内轮廓" or "型腔")
  exclude: questions already covered by equipment_capability (EOC-002 mentions 铣削
    but its expected_family is equipment_capability_records)

drawing_requirement_records:
  trigger: "焊" or "焊缝" or "待焊面" or "焊接符号" or ("符号" and "标准")
```

Mutual exclusion: B1's standard_clause / inspection / equipment_capability
routing must remain unchanged. B2 routing is checked AFTER B1 routing fails,
so B1 questions are never re-routed.

## Implementation sequence

| Work order | Deliverable | Tests |
|---|---|---|
| WO-B2-001 | New records appended to `candidate_seed.json` and `source_manifest.json` | extend existing fixture-shape tests; new `test_b2_record_coverage` |
| WO-B2-002 | `_match_*` functions for 4 new families in `expanded_query.py` | new routing tests for FPS-001/002, MAP-003, DRI-002/003 |
| WO-B2-003 | New `_check_*` contract handlers in `expanded_evaluator.py`; gate test | extend `test_expanded_evaluator_meets_gap_acceptance_gate` to expect ≤ 2 |
| WO-B2-004 | Update README test counts; full regression | none |

## Boundary

Same as B1: the adapter and evaluator remain experimental. Promoting any of
these candidate families to a production retrieval schema is a separate
decision that follows accumulated evidence across multiple drawings.

## Rollback / Preconditions

Preconditions:

- B1 already merged on main (verified: PR #1 merged 2026-05-06).
- All 4 source PDFs available under `references/`:
  GB/T 1804, GB/T 1184, GB/T 324, 工艺知识库.pdf, 金属切削工艺技术手册.pdf.
- Cylinder liner / output shaft / seal sleeve VLM fixtures available
  under `experiments/vlm_source_pdf_process_cards/output/`.

Rollback:

- Revert WO-B2-001..004 commits.
- B1 records and tests are unaffected.
- No production database, OpenClaw runtime, or external service touched.

## Independent design review

Key risks reviewed:

- **Source thinness for D-shape / R4 milling**: the source PDFs do not have a
  dedicated "D 型孔" or "R4 inner radius" page. Records will be paraphrased
  from general feature-process matrix, marked `accepted_with_flags`. Mitigation:
  the question set evaluates contract shape (feature_kind + recommended_processes),
  not literal text match, so paraphrase suffices.
- **Welding symbol catalog risk**: 25+ symbols in one record vs many small
  records. Choosing one lookup-style record keeps the seed size sane and
  matches DRI-003's question shape ("how to interpret welding symbol per GB
  standard"). DRI-002 (待焊面要求) gets its own guidance record because it asks
  about process consequence, not symbol meaning.
- **Routing collision with B1 standard_clause**: GB/T 324 is also a national
  standard. B2 routes welding questions to drawing_requirement_records (not
  standard_clause_records) because the question contracts differ
  (interpretation vs lookup). Routing keyword "焊" is exclusive of B1's GB/T
  1804/1184 keywords. Verified: no question in capability_questions.json
  contains both signals.
- **MAP-003 vs MAP-001 collision**: MAP-001 expects lookup_records (per-pass
  allowance). MAP-003 expects machining_allowance_records (blank-to-finished
  total). Routing must distinguish blank/外径 signal from per-pass allowance.

Decision: proceed.
