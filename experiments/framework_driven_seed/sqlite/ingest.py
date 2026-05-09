"""Ingest framework_driven_seed/data/seed_v1.json into SQLite.

The schema (schema.sql) has two layers:
  - kb_records: header for every record + payload_json
  - std_value_rows: flattened rows from STD records' value_table[]

Mapping rules (heuristic, captures most of seed_v1.json shapes):
  * top-level row dict keys are mapped to typed columns when matching
    canonical names (method / stage / material / workpiece_dim_text /
    workpiece_dim_min / workpiece_dim_max / it / ra_min / ra_max /
    deviation_text / deviation_um / error_text / error_mm_min /
    error_mm_max / feature / method_group)
  * any other row keys go into extra_json
  * size-segment style {min, max, deviation} → workpiece_dim_min/max +
    deviation_um
  * IT range strings like "30~50" or "8-10" → it_min/it_max best-effort
  * size_segments arrays inside result_json get one row per segment

Index records (value_table = []) get a single header in kb_records, no
value rows. Their data is awaiting full extraction in subsequent batches.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = EXPERIMENT_ROOT / "sqlite" / "schema.sql"
SEED_PATH = EXPERIMENT_ROOT / "data" / "seed_v1.json"
DB_PATH = EXPERIMENT_ROOT / "sqlite" / "framework_seed.db"
# Additional seeds (incrementally added; loaded in alpha order after main seed)
EXTRA_SEED_GLOB = "seed_*.json"  # excludes seed_v1.json which is loaded explicitly


_RANGE_RE = re.compile(r"^\s*(-?[\d.]+)\s*[~\-至]\s*(-?[\d.]+)")


def parse_dim_range(text: str | None):
    if not text:
        return None, None
    m = _RANGE_RE.match(str(text))
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            return None, None
    return None, None


def parse_it_range(text: str | None):
    if not text:
        return None, None
    m = re.match(r"^\s*(\d+)\s*[-~]\s*(\d+)", str(text))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^\s*(\d+)\s*$", str(text))
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


_KEY_ALIASES = {
    "IT": "it",
    "IT_min": "it_min",
    "IT_max": "it_max",
    "path": "method",  # 加工路线 → method
    "surface": "feature",  # 表面类型 → feature
    "diameter_le_mm": "workpiece_dim_text",
    "diameter_gt_mm": "workpiece_dim_text",
    "size_min_mm": "workpiece_dim_min",
    "size_max_mm": "workpiece_dim_max",
    "level_code": "stage",
    "kind": "method_group",
    "deviation": "deviation_um",
    "min": "workpiece_dim_min",
    "max": "workpiece_dim_max",
    "length_min": "workpiece_dim_min",
    "length_max": "workpiece_dim_max",
    "d_mm": "workpiece_dim_text",
    "error_mm": "error_text",
    "error_per_L": "error_text",
    "error_per_300": "error_text",
    # ra_um handled by heuristic below (parsed into ra_min/ra_max)
}


def flatten_row(row: dict) -> dict:
    """Convert a value_table row dict into the std_value_rows column shape.

    Recognized keys carry through; alias keys map via _KEY_ALIASES; unrecognized
    keys go to extra_json.
    """
    canonical_keys = {
        "method", "method_group", "feature", "stage", "material",
        "workpiece_dim_text", "workpiece_dim_min", "workpiece_dim_max",
        "workpiece_dim_unit", "it", "it_min", "it_max",
        "ra_min", "ra_max", "deviation_text", "deviation_um",
        "error_text", "error_mm_min", "error_mm_max",
    }
    # Apply alias remapping
    normalized = dict(row)
    for src_key, dst_key in _KEY_ALIASES.items():
        if src_key in normalized and dst_key not in normalized:
            normalized[dst_key] = normalized[src_key]

    flat = {k: normalized.get(k) for k in canonical_keys}
    extra_skip = set(canonical_keys) | set(_KEY_ALIASES.keys()) | {"ra_um"}
    extra = {k: v for k, v in row.items() if k not in extra_skip}

    # Heuristic mappings for shapes seen in seed_v1.json:
    # 1) {min, max, deviation} (size_segments)
    if flat["workpiece_dim_min"] is None and "min" in row and "max" in row:
        flat["workpiece_dim_min"] = row["min"]
        flat["workpiece_dim_max"] = row["max"]
    if flat["deviation_um"] is None and "deviation" in row:
        try:
            flat["deviation_um"] = float(row["deviation"]) * 1000  # mm → μm
        except (TypeError, ValueError):
            pass
    # 2) {length_min, length_max, deviation_text}
    if flat["workpiece_dim_min"] is None and "length_min" in row:
        flat["workpiece_dim_min"] = row.get("length_min")
        flat["workpiece_dim_max"] = row.get("length_max")
    # 3) {d_mm: "≤10"} → workpiece_dim_text
    if flat["workpiece_dim_text"] is None and "d_mm" in row:
        flat["workpiece_dim_text"] = str(row["d_mm"])
    # 4) IT range parse
    if flat["it"] is not None and flat["it_min"] is None:
        lo, hi = parse_it_range(str(flat["it"]))
        flat["it_min"] = lo
        flat["it_max"] = hi
    # 5) error_mm range like "0.04~0.10"
    # error_mm aliases to error_text already, but min/max still need parsing
    if "error_mm" in row and flat["error_mm_min"] is None:
        lo, hi = parse_dim_range(row["error_mm"])
        flat["error_mm_min"] = lo
        flat["error_mm_max"] = hi
    # 6) ra_um range like "0.2~1.6" or "0.4-1.6"
    if "ra_um" in row and flat["ra_min"] is None:
        lo, hi = parse_dim_range(row["ra_um"])
        if lo is not None:
            flat["ra_min"] = lo
            flat["ra_max"] = hi

    return {**flat, "extra_json": json.dumps(extra, ensure_ascii=False) if extra else None}


def _collect_seeds(seed_path: Path) -> list:
    """Load main seed file + any seed_*.json siblings (e.g. seed_cutting_v1.json)."""
    records = json.loads(seed_path.read_text(encoding="utf-8"))
    data_dir = seed_path.parent
    for extra in sorted(data_dir.glob("seed_*.json")):
        if extra.name == seed_path.name:
            continue
        records.extend(json.loads(extra.read_text(encoding="utf-8")))
    return records


def ingest(db_path: Path = DB_PATH, seed_path: Path = SEED_PATH,
           schema_path: Path = SCHEMA_PATH) -> dict:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    cur = conn.cursor()

    seed = _collect_seeds(seed_path)
    record_count = 0
    value_row_count = 0
    index_record_count = 0

    for record in seed:
        cur.execute(
            """
            INSERT INTO kb_records (id, family, prefix, framework_branch, subtype,
                                    topic, source_doc, source_page, source_ref,
                                    source_text, quality_status, quality_flags_json,
                                    tags_json, payload_json)
            VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?)
            """,
            (
                record["id"], record["family"], record["prefix"],
                record["framework_branch"], record.get("subtype"),
                record["topic"], record["source_doc"], record["source_page"],
                record.get("source_ref"), record["source_text"],
                record["quality_status"],
                json.dumps(record.get("quality_flags") or [], ensure_ascii=False),
                json.dumps(record.get("tags") or [], ensure_ascii=False),
                json.dumps(record.get("payload") or {}, ensure_ascii=False),
            ),
        )
        record_count += 1

        if record["family"] != "标准":
            continue
        payload = record.get("payload") or {}
        value_table = payload.get("value_table")
        size_segments = payload.get("size_segments")  # 旧记录直接挂在 payload 上
        if not value_table and not size_segments:
            index_record_count += 1
            continue

        rows = []
        if value_table:
            for vrow in value_table:
                # Expand {feature, methods:[{method, error_mm}, ...]} into one row per inner method
                if isinstance(vrow, dict) and isinstance(vrow.get("methods"), list):
                    parent = {k: v for k, v in vrow.items() if k != "methods"}
                    for inner in vrow["methods"]:
                        if isinstance(inner, dict):
                            rows.append({**parent, **inner})
                else:
                    rows.append(vrow)
        if size_segments:
            for seg in size_segments:
                rows.append({**seg, "method": payload.get("standard"),
                             "method_group": payload.get("kind")})

        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            flat = flatten_row(row)
            cur.execute(
                """
                INSERT INTO std_value_rows
                  (record_id, row_index, method, method_group, feature, stage, material,
                   workpiece_dim_text, workpiece_dim_min, workpiece_dim_max,
                   workpiece_dim_unit, it, it_min, it_max,
                   ra_min, ra_max, deviation_text, deviation_um,
                   error_text, error_mm_min, error_mm_max, extra_json)
                VALUES (?,?, ?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?, ?,?, ?,?,?, ?)
                """,
                (
                    record["id"], i,
                    flat["method"], flat["method_group"], flat["feature"],
                    flat["stage"], flat["material"],
                    flat["workpiece_dim_text"], flat["workpiece_dim_min"],
                    flat["workpiece_dim_max"], flat["workpiece_dim_unit"],
                    flat["it"], flat["it_min"], flat["it_max"],
                    flat["ra_min"], flat["ra_max"],
                    flat["deviation_text"], flat["deviation_um"],
                    flat["error_text"], flat["error_mm_min"], flat["error_mm_max"],
                    flat["extra_json"],
                ),
            )
            value_row_count += 1

    conn.commit()
    conn.close()
    return {
        "db_path": str(db_path),
        "records_ingested": record_count,
        "value_rows_ingested": value_row_count,
        "index_records_no_value_table": index_record_count,
    }


def main() -> int:
    report = ingest()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
