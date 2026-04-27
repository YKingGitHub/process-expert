# Real Drawing Knowledge Planning Report

## Scope

This experiment uses the real test files from:

```text
test-files/
```

Input role:

| File | Role |
| --- | --- |
| `测试.png` | Primary drawing input |
| `设备毛胚信息-随测试图片一起发送.md` | Manufacturing constraints |
| `测试json文件.json` | Auxiliary CAD comparison only |
| `测试结果对照工艺卡.pdf` | Reference answer for evaluation only |

The output is not a final process card. It is a pre-generation knowledge package and gap report.

## Implemented

```text
experiments/real_drawing_knowledge_planning/
```

Key files:

```text
fixtures/drawing_analysis.json
fixtures/equipment_blank.json
fixtures/cad_summary.json
fixtures/reference_route.json
src/planner.py
src/package_builder.py
src/evaluator.py
scripts/vlm_extract_drawing.py
scripts/evaluate.py
```

## Drawing Extraction Result

The drawing PNG VLM fixture captured:

- `φ103`
- `30.5`
- `φ40`
- `φ34 +0.25/0`
- `15 +0.3/0`
- position tolerance `φ0.1 B C`
- roughness `3.2`
- `GB/T1804-2000 m`
- weld surface visual / penetrant inspection requirements

Quality gate result:

```text
drawing_quality.status = needs_review
```

Reason:

```text
missing_critical_drawing_feature: d_shaped_or_milled_inner_profile
```

This means the VLM extraction is useful but not yet sufficient as a trusted drawing parser. It missed the D-shaped / milled inner profile as an explicit feature, even though the dimensions and tolerance frame were extracted.

## Knowledge Planning Result

Command:

```bash
python3 experiments/real_drawing_knowledge_planning/scripts/evaluate.py
```

Summary:

```json
{
  "need_count": 9,
  "usable_need_count": 2,
  "gap_count": 7,
  "blocking_gap_count": 5,
  "route_family_recall": 1.0,
  "route_family_precision": 1.0
}
```

Usable current knowledge:

| Need | Hit |
| --- | --- |
| 基准 / 路线原则 | `PR-DATUM-AXIS-001` |
| Ra 粗糙度参数 | `LU-RA-FINISH-TURN-001` |

Knowledge gaps:

| Need | Candidate Type | Severity |
| --- | --- | --- |
| 位置度 `φ0.1 B C` 解释、加工保证、检验 | `inspection_records` | blocking |
| `GB/T1804-m` 未注公差查询 | `standard_clause_records` | blocking |
| 毛坯 `φ103.5` 到外圆 `φ103` 的余量/装夹 | `machining_allowance_records` | blocking |
| 数控车床 / 三轴加工中心 / 车床能力匹配 | `equipment_capability_records` | blocking |
| D 型孔、`2-R4`、位置度的铣削与检验 | `milling_process_records` | blocking |
| 线切割工序安排 | `wire_cut_process_records` | non-blocking |
| 套类案例命中含 `needs_human_review` | existing case quality issue | non-blocking |

## Reference Route Comparison

Reference route from the actual process card:

```text
领料 -> 车 -> 线切割 -> 车 -> 铣 -> 钳 -> 检验 -> 入库
```

The planner's route-family hypothesis matches the reference operation families:

```text
route_family_recall = 1.0
route_family_precision = 1.0
```

This is only a family-level comparison. It does not validate process parameters, fixture design, cutting data, or final process-card correctness.

## Conclusion

This experiment supports the current direction:

```text
Use a thin Agent planning layer to drive knowledge-base expansion.
```

The real drawing immediately exposes high-priority knowledge gaps that were not visible in the previous 21-question harness. The next knowledge-base work should prioritize:

1. `inspection_records`: GD&T / position tolerance interpretation and inspection.
2. `standard_clause_records`: GB/T1804-m general tolerance tables.
3. `equipment_capability_records`: equipment-to-operation capability mapping.
4. `milling_process_records`: D-shaped hole / profile milling and positional accuracy.
5. `machining_allowance_records`: blank-to-finish allowance for small disc/sleeve parts.
