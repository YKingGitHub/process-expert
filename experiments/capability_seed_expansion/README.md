# Capability Seed Expansion (B1)

This experiment extends the Sprint A capability baseline with source-backed
candidate-family records, then re-runs the capability evaluator to measure
whether the additions actually reduce `gap_count_by_capability`.

## What B1 adds

Three candidate families that the production seed does not yet model:

| Family | Records | Primary source |
|---|---:|---|
| `standard_clause_records` | 25 | GB/T 1804-2000 表1-3 + GB/T 1184-1996 表1-4 + 规则 + 标注语法 |
| `inspection_records` | 4 | `工艺知识库.pdf` p107 prose + GB/T 1184-1996 §5.2/附录A |
| `equipment_capability_records` | 4 | `设备毛胚信息-随测试图片一起发送.md` + general practice paraphrase |

Every record carries `id`, `source_doc`, `source_page`, `source_ref`,
`source_text`, `quality_status`, `quality_flags`, plus one structured payload
(`result_json` / `guidance_json`). `source_manifest.json` records provenance,
evidence type, copyright note, and review status for every record.

## Files

```text
capability_seed_expansion/
├── README.md
├── design.md                     # B1 design (status: approved 2026-05-06)
├── data/
│   ├── candidate_seed.json       # 33 records across 3 families
│   └── source_manifest.json      # 33 provenance entries
├── src/
│   ├── loader.py                 # validate fixture + manifest contracts
│   ├── seed_merge.py             # merge base + candidate without mutation
│   ├── expanded_query.py         # ExpandedKnowledgeQuery candidate routing
│   └── expanded_evaluator.py     # extends CORE_FAMILIES + 3 new contracts
├── scripts/
│   └── evaluate.py               # baseline-vs-expanded comparison report
├── tests/
│   ├── test_capability_seed_expansion.py  # 16 fixture/manifest/merge tests
│   ├── test_expanded_query.py             # 10 routing + delegation tests
│   └── test_expanded_evaluator.py         #  9 evaluator + acceptance gate tests
└── output/
    └── evaluate_report.json      # generated, gitignored
```

## How to run

```bash
# Run the full capability evaluation (baseline vs expanded)
python3 experiments/capability_seed_expansion/scripts/evaluate.py

# Pytest only this experiment
python3 -m pytest experiments/capability_seed_expansion/tests -q

# Full project regression
python3 -m pytest experiments/ -q
```

## Acceptance gates (WO-B1-003)

| Gate | Target | Actual |
|---|---:|---:|
| `expanded_gap_count` | ≤ 8 | **6** |
| `gap_reduction` | (informational) | 5 |
| `real_drawing_mapped_gap_covered_count` | ≥ 2 | **3** |
| Baseline regression | 0 | 0 |
| `needs_human_review` records counted as covered | 0 | 0 |

## Per-capability gap delta

| Capability | Baseline | Expanded | Δ |
|---|---:|---:|---:|
| `drawing_requirement_interpretation` | 3 | 2 | -1 (DRI-001) |
| `equipment_operation_capability` | 2 | 0 | -2 (EOC-002, EOC-003) |
| `geometric_tolerance_inspection` | 2 | 0 | -2 (GTI-001, GTI-003) |
| `feature_process_selection` | 2 | 2 | 0 |
| `deterministic_calculation` | 1 | 1 | 0 |
| `machining_allowance_planning` | 1 | 1 | 0 |
| `route_planning` | 0 | 0 | 0 |

## Boundary

`ExpandedKnowledgeQuery` and `expanded_evaluator` are **experimental**, not
production retrieval. They exist to make capability coverage measurable for
B1. Promoting any candidate family to a production schema is a separate
decision that should be made after evidence accumulates across multiple drawings.

`expanded_gap_count = 6` does not mean "the knowledge base is 6/21 from
done". It means "with these source-backed candidate records routed
deterministically, 5 capability questions transitioned from uncovered to
covered". The remaining six gaps (DRI-002/003 drawing_requirement, FPS-001/002
feature_process & milling, MAP-003 machining_allowance, DCA-003 python
calculation) require either new families (drawing_requirement_records,
feature_process_records, milling_process_records, machining_allowance_records)
or product implementation (DCA-003 needs `process_calc.calculate()` to be
wired and verified).
