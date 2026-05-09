"""Parse 表 4-10 from PDF (page 486) into seed JSON for lookup_size_method_grid.

Run: python3 _parse_4_10.py > /tmp/seed_4_10.json
"""
import json
import re
import sys
import pdfplumber
from pathlib import Path

PDF = Path("/root/ai-assistant/Projects/process-expert/references/金属切削工艺技术手册/手册抽样第4章_机械加工质量控制.pdf")

# IT row top half (16 cols).
TOP_COLS = [
    # (method_label, sub_index, it)
    ("钻及扩钻孔/无钻模",        0, 12),
    ("钻及扩钻孔/有钻模",        0, 11),
    ("扩孔/粗扩",                0, 12),
    ("扩孔/铸孔或冲孔后一次扩孔", 0, 11),
    ("扩孔/粗扩或钻后精扩",      0, 12),  # sub A
    ("扩孔/粗扩或钻后精扩",      1, 12),  # sub B
    ("扩孔/粗扩或钻后精扩",      0, 11),
    ("扩孔/粗扩或钻后精扩",      0, 10),
    ("铰孔/半精铰",              0, 11),
    ("铰孔/半精铰",              0, 10),
    ("铰孔/半精铰",              0,  9),
    ("铰孔/精铰",                0,  8),
    ("铰孔/细铰",                0,  7),
    ("铰孔/细铰",                0,  6),
    ("拉孔/粗拉铸孔或冲孔",      0, 11),
    ("拉孔/粗拉铸孔或冲孔",      0, 10),
]

# IT row bottom half (18 cols).
BOT_COLS = [
    ("拉孔/粗拉孔后或钻孔后精拉孔", 0, 9),
    ("拉孔/粗拉孔后或钻孔后精拉孔", 0, 8),
    ("拉孔/粗拉孔后或钻孔后精拉孔", 0, 7),
    ("镗孔/粗",                    0, 12),
    ("镗孔/半精",                  0, 11),
    ("镗孔/半精",                  0, 10),
    ("镗孔/精",                    0,  9),
    ("镗孔/精",                    0,  8),
    ("镗孔/精",                    0,  7),
    ("镗孔/细",                    0,  6),
    ("磨孔/粗",                    0,  9),
    ("磨孔/粗",                    0,  8),
    ("磨孔/粗",                    0,  7),
    ("磨孔/精",                    0,  6),
    ("用钢球或挤压杆校整、用钢球或滚柱扩孔器挤孔", 0, 10),
    ("用钢球或挤压杆校整、用钢球或滚柱扩孔器挤孔", 0,  9),
    ("用钢球或挤压杆校整、用钢球或滚柱扩孔器挤孔", 0,  8),
    ("用钢球或挤压杆校整、用钢球或滚柱扩孔器挤孔", 0,  7),
]

SIZE_SEGMENTS = [
    # (size_segment_text, size_min, size_max)
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

# Manual fixups for known glued-token rows after pdfplumber extract:
# - row labels ＞120/180/260/360～X glue to first data token
# - rows 11-12 of bottom half glue 3-digit and following 3-digit (215100, 250120)
GLUED_LABEL_PATTERN = re.compile(r"^[＞>]\d+[～~]\d+")


def _split_glued_token(tok: str) -> list[str]:
    """Split glued numerical tokens like '215100' → ['215', '100'] using
    the heuristic that adjacent cells in this table have 3-digit values
    bordering 3-digit values around the same magnitude."""
    if "—" in tok:
        # mixed dash + digits
        parts = re.findall(r"[—\d]+", tok)
        # split runs of digits from dashes
        result = []
        for p in parts:
            # split digit runs of 6 (3+3) ditto
            if p.isdigit() and len(p) >= 4:
                # Heuristic: split into halves at midpoint, biased to leftmost being larger
                mid = len(p) // 2
                # try to detect plausible split
                left = p[:mid+1] if len(p) % 2 == 1 else p[:mid]
                right = p[len(left):]
                result.extend([left, right] if right else [p])
            else:
                result.append(p)
        return result
    if tok.isdigit() and len(tok) >= 5:
        # e.g. '215100' → '215','100' or '250120' → '250','120'
        # split by length: in 4-10 the right cell starts with 1 (IT 10 用钢球)
        # so split at first '1' after position 2
        for i in range(2, len(tok)-1):
            if tok[i] == '1' and len(tok)-i >= 2:
                return [tok[:i], tok[i:]]
        # fallback: equal split
        mid = len(tok) // 2
        return [tok[:mid], tok[mid:]]
    return [tok]


_KNOWN_LABELS = [seg[0] for seg in SIZE_SEGMENTS]


def parse_data_row(line: str, expected_cols: int) -> tuple[str, list[str]]:
    """Return (size_label, data_tokens) where len(data_tokens) == expected_cols."""
    # First, strip whitespace
    line = line.strip()
    # Replace fullwidth ＞ with > and ～ with ~
    line = line.replace("＞", ">").replace("～", "~")
    # Extract leading known size label (longest match wins so '>120~180' beats '>120~18')
    label = None
    rest = line
    for known in sorted(_KNOWN_LABELS, key=len, reverse=True):
        if line.startswith(known):
            label = known
            rest = line[len(known):].lstrip()
            break
    assert label is not None, f"no known size label in line: {line!r}"
    data_raw = rest.split()
    # Now expand glued tokens
    data = []
    for t in data_raw:
        if len(data) >= expected_cols:
            break
        for tt in _split_glued_token(t):
            if tt:
                data.append(tt)
    # Trim or pad
    if len(data) > expected_cols:
        data = data[:expected_cols]
    while len(data) < expected_cols:
        data.append("—")
    return label, data


def main() -> int:
    with pdfplumber.open(PDF) as pdf:
        p = pdf.pages[11]  # 0-indexed; book page 486
        txt = p.extract_text()

    lines = txt.splitlines()

    # Find IT rows
    idx_top_it = None
    idx_bot_it = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("12 11 12 11"):
            idx_top_it = i
        if s.startswith("9 8 7 12 11 10"):
            idx_bot_it = i

    assert idx_top_it is not None and idx_bot_it is not None, "IT rows not found"

    top_rows = []
    for i in range(1, 13):
        ln = lines[idx_top_it + i]
        label, data = parse_data_row(ln, 16)
        top_rows.append((label, data))

    bot_rows = []
    for i in range(1, 13):
        ln = lines[idx_bot_it + i]
        label, data = parse_data_row(ln, 18)
        bot_rows.append((label, data))

    # Validate: labels match SIZE_SEGMENTS texts
    for (label, _), seg in zip(top_rows, SIZE_SEGMENTS):
        # both '1~3' and '1~3' should match (after >→ normalization)
        norm_label = label.replace(">", ">")
        assert norm_label == seg[0] or label == seg[0], f"top label mismatch: {label!r} vs {seg[0]!r}"
    for (label, _), seg in zip(bot_rows, SIZE_SEGMENTS):
        norm_label = label.replace(">", ">")
        assert norm_label == seg[0] or label == seg[0], f"bot label mismatch: {label!r} vs {seg[0]!r}"

    # Build value_table rows
    value_table = []
    row_idx = 0
    for half_name, cols, half_rows in [("top", TOP_COLS, top_rows), ("bot", BOT_COLS, bot_rows)]:
        for seg_i, (size_text, size_min, size_max) in enumerate(SIZE_SEGMENTS):
            label, data = half_rows[seg_i]
            for col_i, (method, sub_idx, it) in enumerate(cols):
                cell = data[col_i]
                if cell == "—":
                    continue
                try:
                    deviation = float(cell)
                except ValueError:
                    print(f"WARN: non-numeric cell at {half_name} {size_text} {method}: {cell!r}", file=sys.stderr)
                    continue
                row = {
                    "size_segment_text": size_text,
                    "size_min": size_min,
                    "size_max": size_max,
                    "method": method,
                    "it_text": str(it),
                    "it_min": it,
                    "it_max": it,
                    "deviation_um_text": cell,
                    "deviation_um_min": deviation,
                    "deviation_um_max": deviation,
                    "extra_json": {
                        "half": half_name,
                        "col_index": col_i,
                        "sub_index": sub_idx,
                    },
                }
                value_table.append(row)
                row_idx += 1

    record = {
        "id": "STD-2.8.1.4-HOLE-ECON-GRID-001",
        "family": "标准",
        "prefix": "STD",
        "framework_branch": "2.8.1.4.HOLE-ECON-GRID",
        "subtype": None,
        "topic": "孔加工的经济精度",
        "source_doc": "金属切削工艺技术手册",
        "source_page": 486,
        "source_ref": "表4-10",
        "source_text": "表4-10 孔加工的经济精度",
        "quality_status": "verified",
        "quality_flags": [],
        "tags": ["Ch4", "size_method_grid", "hole-economic-precision"],
        "payload": {
            "value_table": value_table,
            "notes": [
                "1.孔加工精度与工具的制造精度有关。",
                "2.6级精度细镗孔要采用金刚石工具。",
                "3.用钢球或挤压杆校正适用于孔径≤50mm。",
            ],
        },
    }

    print(json.dumps([record], ensure_ascii=False, indent=2))
    print(f"\n# stats: {len(value_table)} rows extracted from 表4-10", file=sys.stderr)
    # Also print non-dash cell count per half
    top_cells = sum(1 for (l, d) in top_rows for c in d if c != "—")
    bot_cells = sum(1 for (l, d) in bot_rows for c in d if c != "—")
    print(f"# top half non-dash cells: {top_cells} / {16*12}", file=sys.stderr)
    print(f"# bot half non-dash cells: {bot_cells} / {18*12}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
