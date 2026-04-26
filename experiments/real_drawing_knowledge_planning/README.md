# Real Drawing Knowledge Planning POC

Use a real drawing test file to evaluate whether a thin Agent planning layer can:

```text
drawing PNG
  -> structured drawing analysis
  -> knowledge needs
  -> current knowledge query API
  -> knowledge package + gap report
  -> route-family comparison against the reference process card
```

The drawing PNG is the primary input. CAD JSON is only an auxiliary comparison source and is not required for the product path.

External test files:

```text
test-files/测试.png
test-files/测试json文件.json
test-files/测试结果对照工艺卡.pdf
test-files/设备毛胚信息-随测试图片一起发送.md
```

Run:

```bash
python3 experiments/real_drawing_knowledge_planning/scripts/vlm_extract_drawing.py
python3 experiments/real_drawing_knowledge_planning/scripts/evaluate.py
python3 -m pytest experiments/real_drawing_knowledge_planning/tests -q
```

The committed fixtures make tests deterministic. VLM extraction is only needed when refreshing the drawing analysis.

Current expected evaluation summary:

```text
drawing_quality = needs_review
need_count = 9
usable_need_count = 2
gap_count = 7
blocking_gap_count = 5
route_family_recall = 1.0
route_family_precision = 1.0
```

The main outcome is the gap report, not final process-card generation.
