"""Falan pipeline trace — 27 queries.

Source of truth:
  evidence/WO-002-falan-pipeline-trace.md  (in ai-assistant repo)

Each query is a small dict that the runner consumes:
  - id      : "Q01" .. "Q27"
  - step    : "S2" / "S3" / "S4a" / "S4b" / "S4c" / "S5"
  - category: classification of the lookup
  - input   : human-readable input summary
  - text    : query text (for log)
  - kb_call : ("type", *args) — runner dispatches by type
  - expected: text describing what ground truth says the answer should look like
  - assess  : function (actual_dict) -> outcome str ("pass"/"partial"/"no_data"/"friction")

Outcome codes:
  pass     ✅  match expected
  partial  ⚠️  related result returned, needs filtering
  no_data  ❌  empty / not in KB
  friction 🤔  data exists but ad-hoc SQL / extra_json parsing required
"""

from __future__ import annotations
import json


# helpers used by assess fns
def _matches_count(actual, n_min=1):
    return actual.get("match_count", 0) >= n_min


def _empty(actual):
    return actual.get("match_count", 0) == 0


# ---------- Step 2: candidate methods (5) ----------

QUERIES_S2 = [
    {
        "id": "Q01", "step": "S2", "category": "method-candidate",
        "input": "F1 外圆 φ103, IT11, Ra3.2",
        "text": "外圆加工候选路线?",
        "kb_call": ("path_precision", {"path_keyword": "粗车", "feature": "外圆"}),
        "expected": "粗车 (IT11以下/Ra25-100), 粗车→半精车 (IT8-10/Ra6.3-12.5); ground truth 用粗车+半精车",
        "assess": lambda a: "pass" if _matches_count(a, 2) else ("partial" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q02", "step": "S2", "category": "method-candidate",
        "input": "F2 切片厚 31mm 从棒料",
        "text": "切片/截料候选方法?",
        "kb_call": ("raw_sql", "SELECT DISTINCT method FROM std_value_rows WHERE method LIKE '%切%'"),
        "expected": "锯床/线切割/砂轮切割; ground truth 用快走丝线切割",
        "assess": lambda a: "no_data" if _empty(a) else ("partial" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q03", "step": "S2", "category": "method-candidate",
        "input": "F3 沉孔 φ40 × 深 1.5",
        "text": "浅沉孔加工方法?",
        "kb_call": ("economic_precision", {"method": "镗"}),
        "expected": "车端面+车沉孔; ground-truth 用数车铣沉孔",
        "assess": lambda a: "pass" if _matches_count(a, 3) else ("partial" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q04", "step": "S2", "category": "method-candidate",
        "input": "F4 D 型孔 (异形)",
        "text": "异形孔加工方法?",
        "kb_call": ("raw_sql", "SELECT DISTINCT method FROM std_value_rows WHERE method LIKE '%铣%' OR method LIKE '%异形%'"),
        "expected": "三轴加工中心铣 (异形孔很难直接命中)",
        "assess": lambda a: "friction" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q05", "step": "S2", "category": "method-candidate",
        "input": "F5 总长 30.5 端面",
        "text": "平面/端面加工方法?",
        "kb_call": ("path_precision", {"path_keyword": "粗车", "feature": "平面"}),
        "expected": "粗车端面/半精车端面; ground-truth 用车端面",
        "assess": lambda a: "pass" if _matches_count(a, 2) else ("partial" if _matches_count(a, 1) else "no_data"),
    },
]


# ---------- Step 3: precision validation (8) ----------

QUERIES_S3 = [
    {
        "id": "Q06", "step": "S3", "category": "precision-it+ra",
        "input": "F1 路线 '粗车→半精车'",
        "text": "能达到 IT11/Ra3.2?",
        "kb_call": ("path_precision", {"path_keyword": "粗车→半精车"}),
        "expected": "IT 8-10, Ra 6.3-12.5",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q07", "step": "S3", "category": "precision-it+ra",
        "input": "F1 仅粗车",
        "text": "能达到 IT11/Ra3.2?",
        "kb_call": ("path_precision", {"path_keyword": "粗车"}),
        "expected": "粗车单步 IT11以下 Ra25-100, 不够 Ra3.2",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q08", "step": "S3", "category": "precision-ra",
        "input": "F2 线切割 Ra6.3",
        "text": "线切割可达 Ra?",
        "kb_call": ("raw_sql", "SELECT DISTINCT method, ra_min, ra_max FROM std_value_rows WHERE method LIKE '%线切%' OR method LIKE '%电火花%'"),
        "expected": "线切割典型 Ra1.6-12.5",
        "assess": lambda a: "no_data",  # KB 没有线切割记录
    },
    {
        "id": "Q09", "step": "S3", "category": "precision-it",
        "input": "F3 数车沉孔 IT11/Ra3.2",
        "text": "车的经济精度 IT?",
        "kb_call": ("economic_precision", {"method": "车"}),
        "expected": "车 IT9-10, 镗 IT7-8; 满足 IT11",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q10", "step": "S3", "category": "precision-position",
        "input": "F4 铣 D 型孔 形位 ⌖⌀0.1",
        "text": "铣可达位置精度?",
        "kb_call": ("position_error", {"feature": "孔"}),
        "expected": "在坐标镗 0.02-0.04 (best); 加工中心铣 0.1 OK",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q11", "step": "S3", "category": "precision-ra",
        "input": "F4 铣 Ra3.2",
        "text": "铣可达 Ra?",
        "kb_call": ("raw_sql", "SELECT method, ra_min, ra_max FROM std_value_rows WHERE record_id LIKE 'STD-2.8.2.1-RA-MILL%' AND ra_min IS NOT NULL"),
        "expected": "端铣/圆柱铣 Ra1.25-Ra5",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q12", "step": "S3", "category": "precision-ra",
        "input": "F5 车端面 Ra3.2",
        "text": "车端面可达 Ra?",
        "kb_call": ("raw_sql", "SELECT method, stage, material, ra_min, ra_max FROM std_value_rows WHERE record_id = 'STD-2.8.2.1-RA-FACE-TURN-001'"),
        "expected": "车端面 各 stage Ra: 粗车 6.3-12.5 / 半精车 3.2-6.3 / 精车 1.6-6.3 / 精密车 0.4-0.8",
        # method 列全 null, 实际数据靠 record_id + stage 列才能查到 → friction
        "assess": lambda a: "friction" if _matches_count(a, 1) and all(r.get("method") in (None, "") for r in a.get("rows", [])) else ("pass" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q13", "step": "S3", "category": "precision-position",
        "input": "F2 端面 ⊥ 外圆 < 0.1 (线切割保证)",
        "text": "线切割→垂直度 KB 有数据吗?",
        "kb_call": ("raw_sql", "SELECT method, error_text FROM std_value_rows WHERE method LIKE '%线切%' AND error_mm_min IS NOT NULL"),
        "expected": "无数据",
        "assess": lambda a: "no_data",
    },
]


# ---------- Step 4a: allowance (4) — schema v2 via lookup_machining_allowance API ----------

QUERIES_S4A = [
    {
        "id": "Q14", "step": "S4a", "category": "allowance",
        "input": "外圆 φ103, 粗车单边余量",
        "text": "外圆粗车单边余量 typical?",
        "kb_call": ("allowance", {"feature_kind": "外圆", "operation": "粗车", "size_mm": 103}),
        "expected": "外圆 80~120 段, 粗车 2.5 mm 双边 (≤200 长度)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q15", "step": "S4a", "category": "allowance",
        "input": "圆钢 φ103.5 切断",
        "text": "切割余量?",
        "kb_call": ("allowance", {"feature_kind": "切断", "material": "圆钢", "size_mm": 103.5}),
        "expected": "锯床切断 圆钢 100~240 → 8 mm",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q16", "step": "S4a", "category": "allowance",
        "input": "沉孔 φ40 实心铣",
        "text": "沉孔余量分配?",
        "kb_call": ("allowance", {"feature_kind": "孔", "size_mm": 40}),
        "expected": "H7 孔 工序尺寸链 (本表是工序尺寸而非余量, 命中即 pass)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q17", "step": "S4a", "category": "allowance",
        "input": "端面 φ103 长 31",
        "text": "精车端面余量?",
        "kb_call": ("allowance", {"feature_kind": "端面", "operation": "精车", "size_mm": 103, "length_mm": 31}),
        "expected": "50~120 × 18~50: 0.7 mm",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
]


# ---------- Step 4b: cutting params (5) ----------
# After 2026-05-09 schema v2 migration: cutting_params goes through the
# specialized table via lookup_cutting_params API (no json_extract needed).
QUERIES_S4B = [
    {
        "id": "Q18", "step": "S4b", "category": "cutting-params",
        "input": "粗车 304L (奥氏体不锈钢), φ103, 数车",
        "text": "vc/f/ap?",
        "kb_call": ("cutting_params", {
            "material": "不锈钢", "operation": "粗车", "workpiece_dim_text": "100~150"}),
        "expected": "f=0.27-0.81 mm/r, n=185-230 r/min (φ100-150 粗车)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q19", "step": "S4b", "category": "cutting-params",
        "input": "半精车端面, 304L",
        "text": "vc/f/ap 推荐?",
        "kb_call": ("cutting_params", {
            "material": "不锈钢", "operation": "精车", "workpiece_dim_text": "100~150"}),
        "expected": "f=0.1-0.3, n=185-230 (φ100-150 精车)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q20", "step": "S4b", "category": "cutting-params",
        "input": "加工中心铣 D 型孔, 304L 端铣刀",
        "text": "切削三要素 + 主轴转速 + 进给?",
        "kb_call": ("raw_sql",
            "SELECT id FROM kb_records WHERE framework_branch LIKE '2.7%' AND topic LIKE '%铣%'"),
        "expected": "❌ §2.7 暂未含铣削切削参数",
        "assess": lambda a: "no_data",
    },
    {
        "id": "Q21", "step": "S4b", "category": "cutting-params",
        "input": "数车铣沉孔 φ40 深 1.5, 304L",
        "text": "f/ap 推荐?",
        "kb_call": ("cutting_params", {
            "material": "不锈钢", "operation": "精车", "workpiece_dim_text": "40~60"}),
        "expected": "f=0.07-0.2, n=380-480 (φ40-60 精车)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q22", "step": "S4b", "category": "cutting-params",
        "input": "线切割 304L 厚 31",
        "text": "走丝速度 + 脉冲参数?",
        "kb_call": ("raw_sql", "SELECT id FROM kb_records WHERE framework_branch LIKE '2.7%' AND topic LIKE '%线切%'"),
        "expected": "❌ 线切割不在车削手册范围",
        "assess": lambda a: "no_data",
    },
]


# ---------- Step 4c: tolerance chain / lookup (4) ----------

QUERIES_S4C = [
    {
        "id": "Q23", "step": "S4c", "category": "tolerance-chain",
        "input": "外圆 φ103 +0.3/+0.1",
        "text": "ISO 286 能查 IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 103.0, "fit_class": "h8"}),
        "expected": "IT8 公差带 ~54μm; 工件实际带 0.2mm 比 IT8 宽 — 能算但 fit_class 不直接对应",
        "assess": lambda a: "partial" if a.get("ok") else "no_data",
    },
    {
        "id": "Q24", "step": "S4c", "category": "tolerance-chain",
        "input": "沉孔 φ40 +0.3/+0.1",
        "text": "ISO 286 → IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 40.0, "fit_class": "H8"}),
        "expected": "IT8 30-50 段 = 39μm; 工件 0.2mm ≈ IT11+; 越界",
        "assess": lambda a: "partial" if a.get("ok") else "no_data",
    },
    {
        "id": "Q25", "step": "S4c", "category": "tolerance-chain",
        "input": "D 孔 φ34 +0.25/+0.3 (公差带 0.05)",
        "text": "对应 IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 34.0, "fit_class": "H8"}),
        "expected": "IT8 30-50 段 = 39μm; 工件 0.05mm = 50μm ≈ IT9; 答 IT8 不准, 但 process_calc 仅支 H/h/g 6-8",
        "assess": lambda a: "friction" if a.get("ok") else "no_data",
    },
    {
        "id": "Q26", "step": "S4c", "category": "tolerance-chain",
        "input": "工序公差链 (粗车→半精车) 公差分配",
        "text": "extreme_tolerance 算?",
        "kb_call": ("calc", "extreme_tolerance", {
            "components": [
                {"basic_dim": 103.0, "es": 0.3, "ei": 0.1, "role": "increasing"},
                {"basic_dim": 0.0, "es": 0.0, "ei": 0.0, "role": "decreasing"},
            ],
        }),
        "expected": "process_calc 已有 extreme_tolerance 方法",
        "assess": lambda a: "pass" if a.get("ok") else "no_data",
    },
]


# ---------- Step 5: assembly check (1) ----------

QUERIES_S5 = [
    {
        "id": "Q27", "step": "S5", "category": "sequence-check",
        "input": "5 工序候选 vs 8 工序 ground truth",
        "text": "顺序+装夹+合并",
        "kb_call": ("note", "human-only assembly check"),
        "expected": "KB 不负责编排, 仅评估原料完备性",
        "assess": lambda a: "no_data",  # 不算入指标
    },
]

ALL_QUERIES = QUERIES_S2 + QUERIES_S3 + QUERIES_S4A + QUERIES_S4B + QUERIES_S4C + QUERIES_S5
