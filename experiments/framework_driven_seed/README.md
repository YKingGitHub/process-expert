# Framework-Driven Seed (Pilot)

The first framework-driven KB pilot based on the machining design framework v1.1.

Records are extracted **top-down**: the framework v1.1 fixes the spine
(11 categories, 4 families) and textbook chapters fill the leaves. Synthetic
holdout cases validate coverage but do not drive seed content.

## Phase 2 pilot scope (this experiment)

Seven tables / one formula from chapter 4 of `金属切削工艺技术手册`,
chosen because they directly correspond to B4 holdout gaps
(KN-THREAD / KN-PERP / KN-RUNOUT / KN-POSITION):

| Table | Title | Family | Branch |
|---|---|---|---|
| 4-1 | 影响尺寸精度的因素及改善 | 经验 | §2.8.1.1 |
| 4-2 | 影响形状精度的因素及改善 | 经验 | §2.8.1.2 |
| 4-3 | 影响位置精度的因素及改善 | 经验 | §2.8.1.3 |
| 4-19 | 米制螺纹加工的经济精度 | 标准 | §2.4.4 + §2.3.2 |
| 4-31 | 各加工方法可达 Ra | 标准 | §2.8.2.1 |
| 4-32 | 影响切削加工 Ra 因素 | 经验 | §2.8.2.2 |
| 4-33 | 影响磨削 Ra 因素 | 经验 | §2.8.2.2 |

## Files

```
framework_driven_seed/
├── README.md                       # this file
├── data/
│   ├── seed_v1.json                # 90+ structured records
│   └── source_manifest.json        # provenance per record
├── src/
│   ├── __init__.py
│   ├── loader.py                   # validate seed shape per family
│   └── schema.py                   # family-specific record schemas
└── tests/
    └── test_seed.py                # contract tests on records
```

## How to run

```bash
# Validate seed shape
python3 -m pytest experiments/framework_driven_seed/tests -q
```

## Schema (4 families)

All records share base fields:

| Field | Type | Notes |
|---|---|---|
| `id` | str | `{prefix}-{branch}-{topic}-{seq}` per framework v1.1 |
| `family` | str | one of: `经验`, `标准`, `计算`, `案例` |
| `prefix` | str | `EXP` / `STD` / `CALC` / `CASE` |
| `framework_branch` | str | e.g. `2.8.1.1` |
| `subtype` | str | machine-readable subcategory |
| `topic` | str | human-readable Chinese title |
| `source_doc` | str | book title |
| `source_page` | int | textbook page |
| `source_ref` | str | section / table reference |
| `source_text` | str | short verbatim or paraphrase, ≤240 chars |
| `quality_status` | str | `accepted` / `accepted_with_flags` / `needs_human_review` |
| `quality_flags` | str[] | when `accepted_with_flags`, list reasons |
| `tags` | str[] | free tags |

Family-specific payload (one of):

| Family | Field | Shape |
|---|---|---|
| 经验 | `payload` | `{factor, impact, improvement_actions[]}` |
| 标准 | `payload` | `{subject, conditions{}, value, unit, value_table?}` |
| 计算 | `payload` | `{method_id, formula, inputs{}, outputs{}, verified_by_textbook?}` |
| 案例 | `payload` | `{part_name, route_summary, key_lessons[]}` |

## Boundary

- **Pilot only**: 7 tables × 1 chapter, ~90 records. Not the full KB.
- **Standalone pilot**: migration into a larger production knowledge base is a
  separate decision.
