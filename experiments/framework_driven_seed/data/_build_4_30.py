"""Build seed JSON for 表 4-30 (机床形位平均经济精度) — page 493.

The table is irregular (multiple sub-tables, merged cells, machine-specific
metric layouts). Hand-coded data verified against PDF visual + extract_tables
output (see evidence/wo-017B-4-30-machine-geom.txt).

Each (machine_type/subtype, capacity_band, metric_kind, metric_text) is one row.
metric_per_text holds the denominator part (e.g. "100" / "300" / "全长" / "200")
when metric_text is "0.01/100" form; metric_value is the numerator value (mm).

Run: python3 _build_4_30.py > seed_ch4_wo017B_machine_geom_v1.json
"""
import json
import re
import sys

# (machine_type, machine_subtype, capacity_text, capacity_min, capacity_max,
#  metric_kind, metric_text, metric_value, metric_per_text)
ROWS = []


def _add(machine, sub, cap_text, cap_min, cap_max, kind, text, value=None, per=None):
    """Add a row. value and per parsed from text if not given."""
    if value is None and text and text != "—":
        m = re.match(r"^([\d.]+)(?:[／/](.+))?$", text)
        if m:
            try:
                value = float(m.group(1))
            except ValueError:
                pass
            if per is None and m.group(2):
                per = m.group(2)
    ROWS.append({
        "machine_type": machine,
        "machine_subtype": sub,
        "capacity_text": cap_text,
        "capacity_min": cap_min,
        "capacity_max": cap_max,
        "metric_kind": kind,
        "metric_text": text if text else "",
        "metric_value": value,
        "metric_per_text": per,
    })


# === Section 1: 卧式车床 (4 capacities) ===
WC_CAPS = [
    ("≤400",        None,   400.0),
    (">400~800",   400.0,   800.0),
    (">800~1600",  800.0,  1600.0),
    (">1600~3200", 1600.0, 3200.0),
]
WC_YUAN = ["0.01", "0.015", "0.02", "0.025"]              # 圆度
WC_YUAN_ZHU = ["0.0075/100", "0.025/300", "0.03/300", "0.04/300"]  # 圆柱度(长度上)
WC_PING = {
    "≤400":        ["0.015/200", "0.02/300"],
    ">400~800":   ["0.025/400", "0.03/500", "0.04/600"],
    ">800~1600":  ["0.05/700", "0.06/800"],
    ">1600~3200": ["0.07/900", "0.08/1000"],
}
for (ct, cmin, cmax), yd, yz in zip(WC_CAPS, WC_YUAN, WC_YUAN_ZHU):
    _add("卧式车床", "最大加工直径", ct, cmin, cmax, "圆度", yd)
    _add("卧式车床", "最大加工直径", ct, cmin, cmax, "圆柱度(长度上)", yz)
    for pv in WC_PING[ct]:
        _add("卧式车床", "最大加工直径", ct, cmin, cmax, "平面度(凹入)(直径上)", pv)

# === 高精度卧式车床 ===
_add("高精度卧式车床", None, "≤500", None, 500.0, "圆度", "0.005")
_add("高精度卧式车床", None, "≤500", None, 500.0, "圆柱度(长度上)", "0.01/150")
_add("高精度卧式车床", None, "≤500", None, 500.0, "平面度(凹入)(直径上)", "0.01/200")

# === 外圆磨床 (3 capacities, 平面度 = —) ===
WY_CAPS = [
    ("≤200",       None,  200.0),
    (">200~400",  200.0, 400.0),
    (">400~800",  400.0, 800.0),
]
WY_YUAN = ["0.003", "0.004", "0.006"]
WY_YUAN_ZHU = ["0.0055/500", "0.01/1000", "0.015/全长"]
for (ct, cmin, cmax), yd, yz in zip(WY_CAPS, WY_YUAN, WY_YUAN_ZHU):
    _add("外圆磨床", "最大磨削直径", ct, cmin, cmax, "圆度", yd)
    _add("外圆磨床", "最大磨削直径", ct, cmin, cmax, "圆柱度(长度上)", yz)
    # 平面度 = — (skip)

# === 无心磨床 ===
_add("无心磨床", None, None, None, None, "圆度", "0.005")
_add("无心磨床", None, None, None, None, "圆柱度(长度上)", "0.004/100")
_add("无心磨床", None, None, None, None, "平面度(凹入)(直径上)", "等径多边形误差0.003",
     value=0.003, per=None)

# === 珩磨机 ===
_add("珩磨机", None, None, None, None, "圆度", "0.005")
_add("珩磨机", None, None, None, None, "圆柱度(长度上)", "0.01/300")
# 平面度 = — (skip)

# === Section 2: 转塔车床 (4 capacities × 5 metrics) ===
ZT_CAPS = [
    ("≤12",       None,  12.0),
    (">12~32",   12.0,  32.0),
    (">32~80",   32.0,  80.0),
    (">80",      80.0,   None),
]
ZT_DATA = {
    "≤12":     ("0.007", "0.007/300", "0.02/300", "0.04", "0.12"),
    ">12~32":  ("0.01",  "0.01/300",  "0.03/300", "0.05", "0.15"),
    ">32~80":  ("0.01",  "0.02/300",  "0.04/300", "0.06", "0.18"),
    ">80":     ("0.02",  "0.025/300", "0.05/300", "0.09", "0.22"),
}
for ct, cmin, cmax in ZT_CAPS:
    yd, yz, pm, sd, sl = ZT_DATA[ct]
    _add("转塔车床", "最大棒料直径", ct, cmin, cmax, "圆度", yd)
    _add("转塔车床", "最大棒料直径", ct, cmin, cmax, "圆柱度(长度上)", yz)
    _add("转塔车床", "最大棒料直径", ct, cmin, cmax, "平面度(凹入)(直径上)", pm)
    _add("转塔车床", "最大棒料直径", ct, cmin, cmax, "成批工件尺寸的分散度(直径)", sd)
    _add("转塔车床", "最大棒料直径", ct, cmin, cmax, "成批工件尺寸的分散度(长度)", sl)

# === Section 3 卧式镗床 (3 capacities) ===
# 圆度 has 外圆/内孔 split. 平行度 + 垂直度 are merged across all 3 capacities (per visual).
WB_CAPS = [
    ("≤100",      None, 100.0),
    (">100~160", 100.0, 160.0),
    (">160",     160.0, None),
]
WB_DATA = {
    "≤100":     ("0.025", "0.02",  "0.02/200",  "0.04/300"),
    ">100~160": ("0.025", "0.025", "0.025/300", "0.05/500"),
    ">160":     ("0.03",  "0.025", "0.03/400",  "—"),
}
for ct, cmin, cmax in WB_CAPS:
    wy, nh, yz, pm = WB_DATA[ct]
    _add("卧式镗床", "镗杆直径", ct, cmin, cmax, "圆度(外圆)", wy)
    _add("卧式镗床", "镗杆直径", ct, cmin, cmax, "圆度(内孔)", nh)
    _add("卧式镗床", "镗杆直径", ct, cmin, cmax, "圆柱度(长度上)", yz)
    if pm != "—":
        _add("卧式镗床", "镗杆直径", ct, cmin, cmax, "平面度(凹入)(直径上)", pm)
    # 平行度 + 垂直度 merged for all capacities
    _add("卧式镗床", "镗杆直径", ct, cmin, cmax, "孔加工的平行度(长度上)", "0.05/300")
    _add("卧式镗床", "镗杆直径", ct, cmin, cmax, "孔和端面加工的垂直度(长度上)", "0.05/300")

# === 内圆磨床 (3 capacities) ===
NY_CAPS = [
    ("≤50",       None,  50.0),
    (">50~200",  50.0, 200.0),
    (">200",    200.0,  None),
]
NY_DATA = {
    "≤50":      ("0.004",  "0.004/200",  "0.009", "0.015"),
    ">50~200":  ("0.0075", "0.0075/200", "0.013", "0.018"),
    ">200":     ("0.01",   "0.01/200",   "0.02",  "0.022"),
}
for ct, cmin, cmax in NY_CAPS:
    yd, yz, pm, vd = NY_DATA[ct]
    _add("内圆磨床", "最大磨孔直径", ct, cmin, cmax, "圆度", yd)
    _add("内圆磨床", "最大磨孔直径", ct, cmin, cmax, "圆柱度(长度上)", yz)
    _add("内圆磨床", "最大磨孔直径", ct, cmin, cmax, "平面度(凹入)(直径上)", pm)
    # 孔加工的平行度 = — for all 3 (skip)
    _add("内圆磨床", "最大磨孔直径", ct, cmin, cmax, "孔和端面加工的垂直度(长度上)", vd)

# === 立式金刚镗床 ===
_add("立式金刚镗床", None, None, None, None, "圆度", "0.004")
_add("立式金刚镗床", None, None, None, None, "圆柱度(长度上)", "0.01/300")
# 平面度 + 平行度 = — (skip)
_add("立式金刚镗床", None, None, None, None, "孔和端面加工的垂直度(长度上)", "0.03/300")


# Build value_table with extra_json (none for now)
value_table = []
for r in ROWS:
    value_table.append({**r, "extra_json": None})

record = {
    "id": "STD-2.8.1.5-MACHINE-GEOM-001",
    "family": "标准",
    "prefix": "STD",
    "framework_branch": "2.8.1.5.MACHINE-GEOM",
    "subtype": None,
    "topic": "在各种机床上加工时形状、位置的平均经济精度",
    "source_doc": "金属切削工艺技术手册",
    "source_page": 493,
    "source_ref": "表4-30",
    "source_text": "表4-30 在各种机床上加工时形状、位置的平均经济精度",
    "quality_status": "verified",
    "quality_flags": [],
    "tags": ["Ch4", "machine-geometry", "form-error", "position-error"],
    "payload": {
        "value_table": value_table,
        "notes": [],
    },
}

print(json.dumps([record], ensure_ascii=False, indent=2))
print(f"# 4-30: {len(ROWS)} machine-geometry rows", file=sys.stderr)
# Distribution by machine_type
from collections import Counter
c = Counter(r["machine_type"] for r in ROWS)
for k, v in sorted(c.items()):
    print(f"#   {k}: {v}", file=sys.stderr)
