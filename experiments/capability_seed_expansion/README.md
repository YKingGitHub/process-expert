# Capability Seed Expansion (B1 + B2)

This experiment extends the Sprint A capability baseline with source-backed
candidate-family records, then re-runs the capability evaluator to measure
whether the additions actually reduce `gap_count_by_capability`.

Two design rounds have shipped:

| Round | Date | Adds | Result |
|---|---|---|---|
| **B1** | 2026-05-06 | 3 candidate families (standard_clause / inspection / equipment_capability), 33 records | gap 11 → 6, real-drawing 3/7 covered |
| **B2** | 2026-05-06 | 4 candidate families (drawing_requirement / machining_allowance / feature_process / milling_process), 12 records | gap 6 → 1, real-drawing 5/7 covered |

After B2 only DCA-003 (deterministic_calculation, needs Sprint C
`process_calc.calculate()`) and FPS-003 (case_records, optional) remain
uncovered. The two unaddressed real-drawing gaps are KN-WIRECUT-001 (line
wire EDM, B3 territory) and DRAWING-QUALITY-D-SHAPE (Sprint D drawing
parser quality gate).

## Family inventory (after B2)

| Family | Round | Records | Primary source |
|---|---|---:|---|
| `standard_clause_records` | B1 | 25 | GB/T 1804-2000 表1-3 + GB/T 1184-1996 表1-4 + 规则 + 标注语法 |
| `inspection_records` | B1 | 4 | `工艺知识库.pdf` p107 prose + GB/T 1184-1996 §5.2/附录A |
| `equipment_capability_records` | B1 | 4 | `设备毛胚信息-随测试图片一起发送.md` + general practice paraphrase |
| `drawing_requirement_records` | B2 | 3 | **GB/T 324-2008 焊缝符号表示法** §4.1-§4.3 |
| `machining_allowance_records` | B2 | 4 | 缸套/输出轴/密封件定位套 finish-to-grind from `vlm_source_pdf_process_cards` + 工艺知识库 Ch3 |
| `feature_process_records` | B2 | 2 | 金属切削工艺技术手册 Ch6 + general feature-process matrix |
| `milling_process_records` | B2 | 3 | 金属切削工艺技术手册 Ch6 |

**45 candidate records** total (33 B1 + 12 B2), each with `source_doc`,
`source_page`, `source_ref`, `source_text` (≤ 240 chars), `quality_status`,
`quality_flags`, and one of `result_json` / `guidance_json` /
`method_json`. `source_manifest.json` records provenance, evidence type,
copyright note, and review status for every record (45 entries).

## Files

```text
capability_seed_expansion/
├── README.md
├── design.md                     # B1 design (approved 2026-05-06)
├── design_b2.md                  # B2 design (approved 2026-05-06)
├── data/
│   ├── candidate_seed.json       # 45 records across 7 families
│   └── source_manifest.json      # 45 provenance entries
├── src/
│   ├── loader.py                 # validate fixture + manifest contracts
│   ├── seed_merge.py             # merge base + candidate without mutation
│   ├── expanded_query.py         # ExpandedKnowledgeQuery candidate routing (B1+B2)
│   └── expanded_evaluator.py     # extends CORE_FAMILIES + 6 new contracts (B1+B2)
├── scripts/
│   └── evaluate.py               # baseline-vs-expanded comparison report
├── tests/
│   ├── test_capability_seed_expansion.py  # 16 B1 fixture/manifest/merge tests
│   ├── test_expanded_query.py             # 10 B1 routing tests
│   ├── test_expanded_evaluator.py         #  9 B1 evaluator + acceptance gate tests
│   ├── test_b2_seed.py                    #  9 B2 fixture tests
│   ├── test_b2_query.py                   # 13 B2 routing + B1-stability tests
│   └── test_b2_evaluator.py               # 11 B2 evaluator + acceptance gate tests
└── output/
    └── evaluate_report.json      # generated, gitignored
```

## How to run

```bash
# Run the full capability evaluation (baseline vs expanded)
python3 experiments/capability_seed_expansion/scripts/evaluate.py

# Pytest only this experiment (68 tests after B2)
python3 -m pytest experiments/capability_seed_expansion/tests -q

# Full project regression (112 passed after B2)
python3 -m pytest experiments/ -q
```

## Acceptance gates

### B1 (WO-B1-003)

| Gate | Target | Actual |
|---|---:|---:|
| `expanded_gap_count` | ≤ 8 | **6** |
| `real_drawing_mapped_gap_covered_count` | ≥ 2 | **3** |
| Baseline regression | 0 | 0 |
| `needs_human_review` records counted as covered | 0 | 0 |

### B2 (WO-B2-003)

| Gate | Target | Actual |
|---|---:|---:|
| `expanded_gap_count` | ≤ 2 | **1** |
| `gap_reduction` | (informational) | 10 |
| `real_drawing_mapped_gap_covered_count` | ≥ 5 | **5** |
| Baseline regression | 0 | 0 |
| All B1 transitions persist | yes | yes |
| Only DCA-003 remains uncovered | yes | yes |

## Per-capability gap delta (combined B1 + B2)

| Capability | Baseline | After B1 | After B2 | Total Δ |
|---|---:|---:|---:|---:|
| `drawing_requirement_interpretation` | 3 | 2 | 0 | -3 |
| `equipment_operation_capability` | 2 | 0 | 0 | -2 |
| `geometric_tolerance_inspection` | 2 | 0 | 0 | -2 |
| `feature_process_selection` | 2 | 2 | 0 | -2 |
| `machining_allowance_planning` | 1 | 1 | 0 | -1 |
| `deterministic_calculation` | 1 | 1 | 1 | 0 (Sprint C) |
| `route_planning` | 0 | 0 | 0 | 0 |
| **Total** | **11** | **6** | **1** | **-10** |

## Routing order (ExpandedKnowledgeQuery)

```text
1. _match_standard_clause       (B1: GB/T 1804/1184 + 未注公差)
2. _match_inspection            (B1: 位置度/对称度/datum + instrument)
3. _match_equipment             (B1: 数控车床/三轴加工中心/普通车床)
4. _match_drawing_requirement   (B2: 焊 + 焊接符号/待焊面)
5. _match_machining_allowance   (B2: 毛坯 + 余量, excl. 推荐范围/怎么计算)
6. _match_feature_process       (B2: D 型孔/非圆 + 加工选择)
7. _match_milling_process       (B2: 铣 + R/圆角/内轮廓, excl. equipment names)
```

Order matters: B2 routing functions defer to B1 by design (`_match_milling_process`
bails if an equipment name is present so EOC-002 stays with B1
equipment_capability; `_match_machining_allowance` bails on lookup/computation
signals so MAP-001/MAP-002 stay in base families).

## Contract checks added

| Contract | Round | What it verifies |
|---|---|---|
| `standard_clause_lookup` | B1 | `result_json.standard` + `level_code(s)` + citations |
| `inspection_method_with_datum` | B1 | `guidance_json.inspection_method` + `datum_basis` + citations |
| `equipment_operation_match` | B1 | `result_json.equipment_name` + `typical_operations`, OR `guidance_json.assignment_rules` + citations |
| `feature_to_process_contract` | B2 | `result_json.feature_kind` + non-empty `recommended_processes` + citations |
| `allowance_planning_contract` | B2 | `result_json.step_pair` + numeric allowance value + citations |
| `drawing_requirement_interpretation` | B2 | `guidance_json.interpretation` + `applies_to` + citations |

## Boundary

`ExpandedKnowledgeQuery` and `expanded_evaluator` are **experimental**, not
production retrieval. They exist to make capability coverage measurable.
Promoting any candidate family to a production schema is a separate decision
that should be made after evidence accumulates across multiple drawings.

After B2: `expanded_gap_count = 1` does not mean "knowledge base is 1/21
from done". It means "with these 45 source-backed records routed
deterministically, 10 of 11 baseline gaps now satisfy their per-question
contract". The remaining gap (DCA-003) needs Sprint C product implementation,
not seed work.

## Follow-up work

- **Sprint C** — `process_calc.calculate()` Python module → covers DCA-003
- **B3** — `wire_cut_process_records` family → covers KN-WIRECUT-001 (needs
  additional source PDF)
- **Sprint D** — drawing parser quality gate → covers DRAWING-QUALITY-D-SHAPE
- **B4 (held-out drawing)** — second test drawing to validate generalization
  (B1+B2 risk: candidate seeds shaped around real drawing #1)
