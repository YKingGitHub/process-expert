"""Textbook example pipeline trace — 密封件定位套 (Ch3 §3.3.3, 表 3-91).

Source of truth: 金属切削工艺技术手册 Ch3 §3.3.3 "密封件定位套"
Material: HT200 (灰铸铁, 铸件)
Blank:   铸件各部留加工余量 7mm
Main features (per 图 3-7 + 技术要求):
  F1 基准孔 Φ130⁺⁰·⁰⁴⁵⁺⁰·⁰¹⁵ (IT7-8, 同轴度基准)
  F2 外圆 Φ165⁻⁰·¹⁰⁻⁰·¹⁵ (IT11, 同轴度 Φ0.025 对 F1)
  F3 外圆 Φ180⁻⁰·¹⁰⁻⁰·¹⁵ (IT11, 同轴度 Φ0.025 对 F1)
  F4 端面 (垂直度 0.03 对其轴线)
  F5 法兰盘 Φ260 (粗加工)
  F6 总长 220mm
"""

from __future__ import annotations


def _matches_count(actual, n_min=1):
    return actual.get("match_count", 0) >= n_min


def _empty(actual):
    return actual.get("match_count", 0) == 0


# Step 2: candidate methods (5)
QUERIES_S2 = [
    {
        "id": "Q01", "step": "S2", "category": "method-candidate",
        "input": "F1 基准孔 Φ130 IT7, 灰铸铁",
        "text": "内孔基准加工候选路线?",
        "kb_call": ("path_precision", {"path_keyword": "粗镗"}),
        "expected": "粗镗→半精镗→精镗 / 粗镗→半精镗→精磨; ground truth: 粗车→精车→粗磨→精磨",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q02", "step": "S2", "category": "method-candidate",
        "input": "F2/F3 外圆 Φ165/Φ180 IT11, HT200",
        "text": "外圆铸件粗→精车→磨候选路线?",
        "kb_call": ("path_precision", {"path_keyword": "粗车→半精车", "feature": "外圆"}),
        "expected": "粗车 / 粗车→半精车 / 粗车→半精车→精车 系列",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q03", "step": "S2", "category": "method-candidate",
        "input": "F4 端面 (含垂直度 0.03)",
        "text": "端面加工 + 垂直度保证方法?",
        "kb_call": ("path_precision", {"path_keyword": "粗刨"}),
        "expected": "平面表 KB 中 (粗刨/粗铣/车平面)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q04", "step": "S2", "category": "method-candidate",
        "input": "F1 基准孔精磨 (从 ground truth 工序 10)",
        "text": "内圆磨 KB 怎么答?",
        "kb_call": ("raw_sql", "SELECT method, ra_min, ra_max FROM std_value_rows WHERE method LIKE '%磨%' AND ra_min IS NOT NULL"),
        "expected": "内外圆磨/平面磨 method 字段应有数据",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q05", "step": "S2", "category": "method-candidate",
        "input": "F2 外圆磨 (从 ground truth 工序 11)",
        "text": "外圆磨候选?",
        "kb_call": ("path_precision", {"path_keyword": "粗磨→精磨"}),
        "expected": "粗磨→精磨 在 路线表里有",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
]


# Step 3: precision validation (8)
QUERIES_S3 = [
    {
        "id": "Q06", "step": "S3", "category": "precision-it",
        "input": "F1 基准孔 IT7-8",
        "text": "镗孔经济精度 IT?",
        "kb_call": ("economic_precision", {"method": "镗"}),
        "expected": "镗 IT7-9, 精磨 IT5-6",
        "assess": lambda a: "pass" if _matches_count(a, 3) else "no_data",
    },
    {
        "id": "Q07", "step": "S3", "category": "precision-position",
        "input": "F2/F3 外圆 同轴度 Φ0.025 (基准 F1)",
        "text": "外圆同轴度 KB 怎么答?",
        "kb_call": ("economic_precision", {"feature": "同轴度"}),
        "expected": "STD-2.8.1.4-COAXIALITY-ECON-001 应能命中",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q08", "step": "S3", "category": "precision-position",
        "input": "F4 端面垂直度 0.03 对其轴线",
        "text": "端面垂直度 KB 怎么答?",
        "kb_call": ("economic_precision", {"feature": "垂直度"}),
        "expected": "STD-2.8.1.4-RUNOUT-PERP-ECON-001 (端面圆跳动+垂直度) 应命中",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q09", "step": "S3", "category": "precision-it+ra",
        "input": "F1 路线 '粗车→精车→粗磨→精磨'",
        "text": "孔类该路线 IT/Ra?",
        "kb_call": ("path_precision", {"path_keyword": "粗车→半精车→精车 (或磨)"}),
        "expected": "外圆同等路线 IT 7-8 / Ra 1.6-6.3; 孔类应类似 (KB 内孔表 STD-2.3.2-LATHE-HOLE-PATH-001)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q10", "step": "S3", "category": "precision-ra",
        "input": "F1 内孔精磨 Ra (gt 工序 10 给 Ra 隐式)",
        "text": "内圆磨 Ra?",
        "kb_call": ("raw_sql", "SELECT method, ra_min, ra_max FROM std_value_rows WHERE record_id = 'STD-2.8.2.1-RA-GRIND-OD-001'"),
        "expected": "内外圆磨 Ra (但 method 列可能为 null)",
        "assess": lambda a: "friction" if _matches_count(a, 1) and all(r.get("method") in (None, "") for r in a.get("rows", [])) else ("pass" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q11", "step": "S3", "category": "precision-ra",
        "input": "F4 平面磨端面 Ra",
        "text": "平面磨可达 Ra?",
        "kb_call": ("raw_sql", "SELECT method, ra_min, ra_max FROM std_value_rows WHERE record_id = 'STD-2.8.2.1-RA-GRIND-FLAT-001'"),
        "expected": "平面磨 Ra (method 列可能 null)",
        "assess": lambda a: "friction" if _matches_count(a, 1) and all(r.get("method") in (None, "") for r in a.get("rows", [])) else ("pass" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q12", "step": "S3", "category": "precision-ra",
        "input": "F2 路线 '粗车→半精车→精车' Ra",
        "text": "外圆精车 Ra?",
        "kb_call": ("path_precision", {"path_keyword": "粗车→半精车→精车 (或磨)"}),
        "expected": "Ra 1.6-6.3",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q13", "step": "S3", "category": "precision-position",
        "input": "F1 基准孔 → 同轴度链 (位置度的累计)",
        "text": "同轴度 Φ0.025 加工方法位置精度?",
        "kb_call": ("position_error", {"feature": "孔与孔之间"}),
        "expected": "孔位置精度表 STD-2.3.2-METHOD-ERRORS-001 含相关行",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
]


# Step 4a: allowance (4)
QUERIES_S4A = [
    {
        "id": f"Q1{i}", "step": "S4a", "category": "allowance",
        "input": txt[0], "text": txt[1],
        "kb_call": ("raw_sql", "SELECT id FROM kb_records WHERE framework_branch LIKE '2.9.1%'"),
        "expected": "❌ Ch6 余量表还没抽",
        "assess": lambda a: "no_data",
    } for i, txt in enumerate([
        ("铸件余量 7mm 总, 各序分配 (5mm + 0.5mm + 0.05mm 大致)", "粗+精+磨 内孔余量分配?"),
        ("外圆 Φ180 - 留 5mm 粗 - 0.5mm 精 - ?磨", "外圆磨余量?"),
        ("端面磨 0.4mm/序", "端面磨余量?"),
        ("总长 220mm 各序加工余量", "总长余量?"),
    ], start=4)
]


# Step 4b: cutting params (5)
QUERIES_S4B = [
    {
        "id": f"Q{i}", "step": "S4b", "category": "cutting-params",
        "input": txt[0], "text": txt[1],
        "kb_call": ("raw_sql", "SELECT id FROM kb_records WHERE framework_branch LIKE '2.7%'"),
        "expected": "❌ Ch3 §3.2 / §2.7 切削参数还没抽",
        "assess": lambda a: "no_data",
    } for i, txt in enumerate([
        ("CA6163 粗车 HT200 Φ180 → Φ175", "vc/f/ap?"),
        ("精车 HT200 Φ165 +0.5mm 留磨", "vc/f/ap?"),
        ("内圆磨 HT200 Φ130 IT7", "磨削参数 (砂轮+vc+f)?"),
        ("平面磨端面 HT200", "磨削参数?"),
        ("精车法兰盘端面 HT200 Φ260", "vc/f/ap?"),
    ], start=18)
]


# Step 4c: tolerance (4)
QUERIES_S4C = [
    {
        "id": "Q23", "step": "S4c", "category": "tolerance-chain",
        "input": "基准孔 Φ130⁺⁰·⁰⁴⁵⁺⁰·⁰¹⁵",
        "text": "ISO 286 fit_class IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 130.0, "fit_class": "H7"}),
        "expected": "H7 120-180 段 = 40μm; 工件 0.030mm = 30μm ≈ IT7",
        "assess": lambda a: "pass" if a.get("ok") else "no_data",
    },
    {
        "id": "Q24", "step": "S4c", "category": "tolerance-chain",
        "input": "外圆 Φ165⁻⁰·¹⁰⁻⁰·¹⁵",
        "text": "ISO 286 → IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 165.0, "fit_class": "h8"}),
        "expected": "h8 120-180 段 = 63μm; 工件 0.05mm = 50μm; IT8 接近",
        "assess": lambda a: "partial" if a.get("ok") else "no_data",
    },
    {
        "id": "Q25", "step": "S4c", "category": "tolerance-chain",
        "input": "外圆 Φ180⁻⁰·¹⁰⁻⁰·¹⁵",
        "text": "ISO 286 → IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 180.0, "fit_class": "h8"}),
        "expected": "h8 180-250 段 = 72μm; 工件 50μm",
        "assess": lambda a: "partial" if a.get("ok") else "no_data",
    },
    {
        "id": "Q26", "step": "S4c", "category": "tolerance-chain",
        "input": "公差链 (粗车→精车→粗磨→精磨)",
        "text": "extreme_tolerance?",
        "kb_call": ("calc", "extreme_tolerance", {
            "components": [
                {"basic_dim": 130.0, "es": 0.045, "ei": 0.015, "role": "increasing"},
                {"basic_dim": 0.0, "es": 0.0, "ei": 0.0, "role": "decreasing"},
            ],
        }),
        "expected": "process_calc 已有",
        "assess": lambda a: "pass" if a.get("ok") else "no_data",
    },
]


# Step 5: assembly (1)
QUERIES_S5 = [
    {
        "id": "Q27", "step": "S5", "category": "sequence-check",
        "input": "5 工序候选 vs 13 工序 ground truth",
        "text": "顺序+装夹+合并",
        "kb_call": ("note", "human-only"),
        "expected": "KB 不负责编排",
        "assess": lambda a: "no_data",
    },
]

ALL_QUERIES = QUERIES_S2 + QUERIES_S3 + QUERIES_S4A + QUERIES_S4B + QUERIES_S4C + QUERIES_S5
