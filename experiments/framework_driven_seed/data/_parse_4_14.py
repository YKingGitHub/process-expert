"""Parse 表 4-14 from PDF (pages 487-488) into seed JSON for lookup_size_method_grid.

Structure: 14 IT cols × 12 size segments. Col 0 (粗车 IT 12-13) shows
deviation ranges (e.g. "340~620") for sizes >30~50 and larger.

Run: python3 _parse_4_14.py > seed_ch4_wo015b_outer_cyl_grid_v1.json
"""
import json
import re
import sys
import pdfplumber
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PDF = REPO_ROOT / "references" / "金属切削工艺技术手册" / "手册抽样第4章_机械加工质量控制.pdf"

# 14 IT cols.
COLS = [
    # (method_label, it_text, it_min, it_max)
    ("车削/粗车",                                    "12~13", 12, 13),
    ("车削/半精车或一次加工",                        "12",    12, 12),
    ("车削/半精车或一次加工",                        "11",    11, 11),
    ("车削/精车",                                    "10",    10, 10),
    ("车削/精车",                                    "9",      9,  9),
    ("磨削/一次加工",                                "7",      7,  7),
    ("磨削/粗磨",                                    "9",      9,  9),
    ("磨削/粗磨",                                    "7",      7,  7),
    ("磨削/精磨",                                    "6",      6,  6),
    ("研磨",                                          "5",      5,  5),
    ("用钢珠或滚柱工具滚压",                          "10",    10, 10),
    ("用钢珠或滚柱工具滚压",                          "9",      9,  9),
    ("用钢珠或滚柱工具滚压",                          "7",      7,  7),
    ("用钢珠或滚柱工具滚压",                          "6",      6,  6),
]

SIZE_SEGMENTS = [
    ("1~3",      1.0,    3.0),
    (">3~6",     3.0,    6.0),
    (">6~10",    6.0,   10.0),
    (">10~18",  10.0,   18.0),
    (">18~30",  18.0,   30.0),
    (">30~50",  30.0,   50.0),
    (">50~80",  50.0,   80.0),
    (">80~120", 80.0,  120.0),
    (">120~180",120.0, 180.0),
    (">180~260",180.0, 260.0),
    (">260~360",260.0, 360.0),
    (">360~500",360.0, 500.0),
]

_KNOWN_LABELS = [seg[0] for seg in SIZE_SEGMENTS]


def parse_data_row(line: str, expected_cols: int = 14) -> tuple[str, list[str]]:
    line = line.strip().replace("＞", ">").replace("～", "~")
    label = None
    rest = line
    for known in sorted(_KNOWN_LABELS, key=len, reverse=True):
        if line.startswith(known):
            label = known
            rest = line[len(known):].lstrip()
            break
    assert label is not None, f"no known size label in line: {line!r}"
    raw = rest.split()
    # Expand glued tokens. Two heuristics:
    # (a) glue between '>120~180' and first numeric was already removed by lstrip
    # (b) col 0 values may contain '~' (e.g. "340~620") — keep as-is
    # (c) numeric runs like "215100" need splitting (none expected in 4-14, but defensive)
    data = []
    for t in raw:
        if "~" in t:
            data.append(t)  # keep range as single token
        elif t.isdigit() and len(t) >= 5 and not t.startswith("1"):
            # split heuristic: at first '1' from middle
            for i in range(2, len(t) - 1):
                if t[i] == "1":
                    data.extend([t[:i], t[i:]])
                    break
            else:
                mid = len(t) // 2
                data.extend([t[:mid], t[mid:]])
        else:
            data.append(t)
        if len(data) >= expected_cols:
            break
    while len(data) < expected_cols:
        data.append("—")
    return label, data[:expected_cols]


def parse_value(cell: str) -> tuple[str | None, float | None, float | None]:
    """Return (text, min, max) for a cell. '—' → (None, None, None)."""
    cell = cell.replace("～", "~")
    if cell == "—" or cell == "" or cell == "-":
        return None, None, None
    if "~" in cell:
        m = re.match(r"^(-?[\d.]+)~(-?[\d.]+)$", cell)
        if m:
            return cell, float(m.group(1)), float(m.group(2))
        return cell, None, None
    try:
        v = float(cell)
        return cell, v, v
    except ValueError:
        return cell, None, None


def main() -> int:
    with pdfplumber.open(PDF) as pdf:
        text_487 = pdf.pages[12].extract_text()
        text_488 = pdf.pages[13].extract_text()

    # Locate IT row line in each page; data rows follow until non-size-label row.
    rows = []  # (size_label, data_tokens)
    for txt in (text_487, text_488):
        lines = txt.splitlines()
        for i, ln in enumerate(lines):
            s = ln.strip().replace("＞", ">").replace("～", "~")
            if s.startswith("12~13 12 11 10 9 7 9 7 6 5"):
                # data follows
                for j in range(i + 1, len(lines)):
                    s2 = lines[j].strip().replace("＞", ">").replace("～", "~")
                    if not s2:
                        continue
                    # stop on next table or section
                    if s2.startswith("表4-") or "（续）" in s2 or "金属切削" in s2:
                        break
                    # only accept if it starts with a known size label (after normalization)
                    matched = False
                    for known in _KNOWN_LABELS:
                        if s2.startswith(known):
                            matched = True
                            break
                    if matched:
                        label, data = parse_data_row(lines[j])
                        rows.append((label, data))
                    else:
                        break
                break

    # Sort rows by size_min for stability
    seg_index = {s[0]: i for i, s in enumerate(SIZE_SEGMENTS)}
    rows.sort(key=lambda x: seg_index.get(x[0], 999))

    # Build value_table
    value_table = []
    cells_total = 0
    cells_filled = 0
    for label, data in rows:
        seg = next((s for s in SIZE_SEGMENTS if s[0] == label), None)
        if seg is None:
            print(f"WARN: unknown size label {label!r}", file=sys.stderr)
            continue
        for ci, (method, it_text, it_min, it_max) in enumerate(COLS):
            cells_total += 1
            cell = data[ci]
            text, vmin, vmax = parse_value(cell)
            if vmin is None:
                continue
            cells_filled += 1
            value_table.append({
                "size_segment_text": seg[0],
                "size_min": seg[1],
                "size_max": seg[2],
                "method": method,
                "it_text": it_text,
                "it_min": it_min,
                "it_max": it_max,
                "deviation_um_text": text,
                "deviation_um_min": vmin,
                "deviation_um_max": vmax,
                "extra_json": {
                    "col_index": ci,
                },
            })

    record = {
        "id": "STD-2.8.1.4-OUTER-CYL-ECON-GRID-001",
        "family": "标准",
        "prefix": "STD",
        "framework_branch": "2.8.1.4.OUTER-CYL-ECON-GRID",
        "subtype": None,
        "topic": "外圆柱表面加工的经济精度",
        "source_doc": "金属切削工艺技术手册",
        "source_page": 487,
        "source_ref": "表4-14",
        "source_text": "表4-14 外圆柱表面加工的经济精度",
        "quality_status": "verified",
        "quality_flags": [],
        "tags": ["Ch4", "size_method_grid", "outer-cylinder-economic-precision"],
        "payload": {
            "value_table": value_table,
            "notes": [],
        },
    }
    print(json.dumps([record], ensure_ascii=False, indent=2))
    print(f"# 4-14: {cells_filled} / {cells_total} cells filled (12 sizes × 14 IT cols)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
