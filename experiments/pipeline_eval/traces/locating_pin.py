"""Locating-pin pipeline trace — 27 queries.

Source of truth: 定位销工艺规程.pdf (XX-XXX-6DH00A B版, 6 工序)
Material: Z2CND18-12NS (奥氏体不锈钢, 类似 316L)
Blank:    φ26 × 980 棒料 (一件毛坯加工 10 件)
Main features:
  F1 螺纹 M14-6g (大径 φ14⁻⁰·⁰³⁸⁻⁰·³⁸⁸)
  F2 外圆 φ21.74⁺⁰·⁰⁵, Ra1.6, 形位 ⌖φ0.1 B
  F3 锥面 25°±1°
  F4 球面 SR5.33 / R6.35
  F5 铣扁 19±0.025, Ra3.2, 形位 ⌖0.12 C
  F6 总长 + 端面
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
        "input": "F2 外圆 φ21.74 +0.05, IT9, Ra1.6",
        "text": "外圆精车候选路线?",
        "kb_call": ("path_precision", {"path_keyword": "粗车→半精车→精车", "feature": "外圆"}),
        "expected": "粗车→半精车→精车 (IT 7-8, Ra 1.6-6.3)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q02", "step": "S2", "category": "method-candidate",
        "input": "F1 螺纹 M14-6g (螺距 2)",
        "text": "螺纹加工候选方法?",
        "kb_call": ("raw_sql", "SELECT id, topic FROM kb_records WHERE framework_branch LIKE '2.4.4%' OR topic LIKE '%螺纹%'"),
        "expected": "螺纹: 数控车挑螺纹 / 螺纹梳刀 / 滚丝; ground truth 用挑螺纹",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q03", "step": "S2", "category": "method-candidate",
        "input": "F4 球面 SR5.33 / R6.35",
        "text": "球面/曲面加工方法?",
        "kb_call": ("raw_sql", "SELECT DISTINCT method FROM std_value_rows WHERE method LIKE '%球%' OR method LIKE '%成形%'"),
        "expected": "数车成形车刀 / 仿形车 / 五轴铣; ground truth 用数车车球面",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q04", "step": "S2", "category": "method-candidate",
        "input": "F3 锥面 25°",
        "text": "锥面加工方法?",
        "kb_call": ("raw_sql", "SELECT id, topic FROM kb_records WHERE topic LIKE '%锥%'"),
        "expected": "数车锥度车刀 / 偏置尾座车 / 转角刀架; ground truth 用数车车锥面",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q05", "step": "S2", "category": "method-candidate",
        "input": "F5 铣扁 19±0.025 (形位 ⌖0.12)",
        "text": "面铣 (扁) 加工方法?",
        "kb_call": ("path_precision", {"path_keyword": "粗铣"}),
        "expected": "粗铣→半精铣 (IT8-11)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
]


# Step 3: precision validation (8)
QUERIES_S3 = [
    {
        "id": "Q06", "step": "S3", "category": "precision-it+ra",
        "input": "F2 路线 '粗车→半精车→精车' 能达 IT9 Ra1.6?",
        "text": "外圆该路线 IT/Ra?",
        "kb_call": ("path_precision", {"path_keyword": "粗车→半精车→精车"}),
        "expected": "IT 7-8, Ra 1.6-6.3 (满足要求, IT9 比 IT7-8 宽容)",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q07", "step": "S3", "category": "precision-it",
        "input": "F1 螺纹 6g 等级 (中等精度)",
        "text": "M14-6g 螺纹精度 KB 中?",
        "kb_call": ("raw_sql", "SELECT row_index, method, extra_json FROM std_value_rows WHERE record_id = 'STD-2.4.4-THREAD-METRIC-001'"),
        "expected": "螺纹精度表里 6g 是常用外螺纹",
        "assess": lambda a: "friction" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q08", "step": "S3", "category": "precision-ra",
        "input": "F5 铣扁 Ra3.2",
        "text": "铣可达 Ra?",
        "kb_call": ("raw_sql", "SELECT method, ra_min, ra_max FROM std_value_rows WHERE record_id LIKE 'STD-2.8.2.1-RA-MILL%' AND ra_min IS NOT NULL"),
        "expected": "端铣 Ra1.25-5, 圆柱铣 Ra1.6-12.5",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q09", "step": "S3", "category": "precision-position",
        "input": "F2 形位 ⌖φ0.1 B (位置度)",
        "text": "车的位置精度 KB 怎么答?",
        "kb_call": ("position_error", {"feature": "外圆"}),
        "expected": "外圆同轴/位置精度 — KB 主要是位置度孔的, 外圆少",
        "assess": lambda a: "partial" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q10", "step": "S3", "category": "precision-position",
        "input": "F5 铣扁 形位 ⌖0.12 C",
        "text": "铣扁位置精度?",
        "kb_call": ("position_error", {"feature": "扁"}),
        "expected": "无 '扁' feature 表; 实际靠夹具+找正保证",
        "assess": lambda a: "no_data",
    },
    {
        "id": "Q11", "step": "S3", "category": "precision-ra",
        "input": "F2 精车外圆 Ra1.6",
        "text": "精车 Ra?",
        "kb_call": ("raw_sql", "SELECT row_index, method, stage, ra_min, ra_max FROM std_value_rows WHERE record_id = 'STD-2.8.2.1-RA-OD-TURN-001'"),
        "expected": "外圆车 各 stage Ra; 但 method 列可能为 null",
        "assess": lambda a: "friction" if _matches_count(a, 1) and all(r.get("method") in (None, "") for r in a.get("rows", [])) else ("pass" if _matches_count(a, 1) else "no_data"),
    },
    {
        "id": "Q12", "step": "S3", "category": "precision-ra",
        "input": "F1 车螺纹 Ra3.2",
        "text": "车螺纹可达 Ra?",
        "kb_call": ("path_precision", {"path_keyword": "车螺纹"}),
        "expected": "车螺纹 Ra 数据应该在 STD-2.8.2.1-RA-THREAD-001",
        "assess": lambda a: "pass" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q13", "step": "S3", "category": "precision-it",
        "input": "F2 数车精车 (经济精度)",
        "text": "车的经济精度 IT?",
        "kb_call": ("economic_precision", {"method": "车"}),
        "expected": "车 IT9-10, 精车更高",
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
        ("毛坯 φ26 → 加工后 φ21.74, 单边 ~2.13mm", "外圆粗车→半精车→精车 各序余量?"),
        ("螺纹大径 φ14 (车出来), 起始 φ14.5?", "螺纹大径前余量?"),
        ("总长 92.5 切断, 切刀≤3mm", "切断余量 + 端面修整余量?"),
        ("铣扁 19mm 从 φ21.74 减薄, 单边 ~1.37mm", "铣扁余量?"),
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
        ("粗车 316L, φ26 → φ21.74, 数车", "vc/f/ap?"),
        ("挑螺纹 M14×2, 316L", "螺纹切削参数 + 挑数?"),
        ("数车成形球面 SR5.33, 316L", "f/ap (成形)?"),
        ("加工中心铣扁 19, 316L 端铣刀", "切削三要素 + 主轴转速?"),
        ("数车锥面 25°, 316L", "vc/f 推荐?"),
    ], start=18)
]


# Step 4c: tolerance chain / lookup (4)
QUERIES_S4C = [
    {
        "id": "Q23", "step": "S4c", "category": "tolerance-chain",
        "input": "外圆 φ21.74 +0.05/0",
        "text": "ISO 286 fit_class IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 21.74, "fit_class": "h7"}),
        "expected": "h7 18-30 段 = 21μm; 工件 0.05mm = 50μm ≈ IT9; h7 不够紧",
        "assess": lambda a: "partial" if a.get("ok") else "no_data",
    },
    {
        "id": "Q24", "step": "S4c", "category": "tolerance-chain",
        "input": "铣扁 19±0.025 (公差带 0.05)",
        "text": "ISO 286 → IT?",
        "kb_call": ("calc", "tolerance_lookup_iso", {"diameter_mm": 19.0, "fit_class": "h8"}),
        "expected": "IT8 18-30 段 = 33μm; 工件 50μm ≈ IT9-10",
        "assess": lambda a: "partial" if a.get("ok") else "no_data",
    },
    {
        "id": "Q25", "step": "S4c", "category": "tolerance-chain",
        "input": "螺纹 M14-6g 大径 φ14⁻⁰·⁰³⁸⁻⁰·³⁸⁸",
        "text": "螺纹 6g 公差 KB 能算?",
        "kb_call": ("raw_sql", "SELECT row_index, method, extra_json FROM std_value_rows WHERE record_id = 'STD-2.4.4-THREAD-METRIC-001' LIMIT 3"),
        "expected": "螺纹精度表 KB 内, 但需读 extra_json",
        "assess": lambda a: "friction" if _matches_count(a, 1) else "no_data",
    },
    {
        "id": "Q26", "step": "S4c", "category": "tolerance-chain",
        "input": "工序公差链 (粗车→半精车→精车) 公差分配",
        "text": "extreme_tolerance 算?",
        "kb_call": ("calc", "extreme_tolerance", {
            "components": [
                {"basic_dim": 21.74, "es": 0.05, "ei": 0.0, "role": "increasing"},
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
        "input": "5 工序候选 vs 6 工序 ground truth",
        "text": "顺序+装夹+合并",
        "kb_call": ("note", "human-only assembly check"),
        "expected": "KB 不负责编排",
        "assess": lambda a: "no_data",
    },
]

ALL_QUERIES = QUERIES_S2 + QUERIES_S3 + QUERIES_S4A + QUERIES_S4B + QUERIES_S4C + QUERIES_S5
