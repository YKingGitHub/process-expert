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


_RA_METHOD_FROM_TOPIC_RE = re.compile(r"^([一-鿿]+)\s+加工方法可达表面粗糙度")


def _dispatch_specialized(record):
    """Return (target_table, prepared_rows) or (None, []) for non-applicable.

    target_table is one of:
      lookup_path_precision, lookup_method_economic_it, lookup_method_position_error,
      lookup_method_ra, lookup_surface_ra, lookup_cutting_params
      None for records whose shape doesn't fit any specialized table
      (螺纹精度 / 加工硬化 / 圆锥孔 / 型面 — payload-only).
    """
    if record["family"] != "标准":
        return None, []
    branch = record["framework_branch"]
    rid = record["id"]
    payload = record.get("payload") or {}
    value_table = payload.get("value_table") or []
    size_segments = payload.get("size_segments")
    if not value_table and not size_segments:
        return None, []  # index-only record

    rows = []
    if value_table:
        for vrow in value_table:
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

    if branch.startswith("2.3.2") and "PATH" in rid:
        return "lookup_path_precision", _build_path_rows(record, rows)
    if rid == "STD-2.3.2-METHOD-ERRORS-001":
        return "lookup_method_position_error", _build_pos_err_rows(record, rows)
    if branch.startswith("2.8.1.4") and "POS-ECON" in rid:
        return "lookup_method_position_error", _build_pos_err_rows(record, rows)
    if branch.startswith("2.8.1.4"):
        return "lookup_method_economic_it", _build_econ_it_rows(record, rows)
    if branch.startswith("2.8.2.1"):
        return "lookup_method_ra", _build_method_ra_rows(record, rows)
    if branch.startswith("2.8.2.4"):
        return "lookup_surface_ra", _build_surface_ra_rows(record, rows)
    if branch.startswith("2.7"):
        return "lookup_cutting_params", _build_cutting_rows(record, rows)
    return None, []  # specialized records → payload-only


def _build_path_rows(record, rows):
    topic = record["topic"]
    feature_kind = (
        "外圆" if "外圆" in topic else
        "孔" if "孔" in topic else
        "平面" if "平面" in topic else None
    )
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        path_text = row.get("path") or row.get("method") or ""
        it_text = row.get("IT") or row.get("it")
        it_min, it_max = parse_it_range(it_text) if it_text else (None, None)
        ra_min = ra_max = None
        if "ra_um" in row:
            ra_min, ra_max = parse_dim_range(row["ra_um"])
        elif "ra_min" in row:
            ra_min, ra_max = row.get("ra_min"), row.get("ra_max")
        extras = {k: v for k, v in row.items()
                  if k not in {"path", "method", "IT", "it", "ra_um",
                               "ra_min", "ra_max", "solid", "preformed"}}
        out.append({
            "record_id": record["id"], "row_index": i,
            "feature_kind": feature_kind, "path_text": path_text,
            "it_text": it_text, "it_min": it_min, "it_max": it_max,
            "ra_min": ra_min, "ra_max": ra_max,
            "applies_to_solid": 1 if row.get("solid") else None,
            "applies_to_preformed": 1 if row.get("preformed") else None,
            "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
        })
    return out


def _build_econ_it_rows(record, rows):
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        it_text = row.get("IT") or row.get("it")
        it_min = row.get("IT_min") or row.get("it_min")
        it_max = row.get("IT_max") or row.get("it_max")
        if it_min is None and it_text:
            it_min, it_max = parse_it_range(it_text)
        extras = {k: v for k, v in row.items()
                  if k not in {"method", "feature", "IT", "it",
                               "IT_min", "IT_max", "it_min", "it_max"}}
        out.append({
            "record_id": record["id"], "row_index": i,
            "method": row.get("method") or row.get("path") or "?",
            "feature": row.get("feature"),
            "it_text": it_text,
            "it_min": int(it_min) if it_min is not None else None,
            "it_max": int(it_max) if it_max is not None else None,
            "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
        })
    return out


def _build_pos_err_rows(record, rows):
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        err_text = row.get("error_mm") or row.get("error_text")
        err_min, err_max = parse_dim_range(err_text) if err_text else (None, None)
        extras = {k: v for k, v in row.items()
                  if k not in {"method", "feature", "error_mm", "error_text"}}
        out.append({
            "record_id": record["id"], "row_index": i,
            "method": row.get("method") or "?",
            "feature": row.get("feature"),
            "error_text": err_text,
            "error_mm_min": err_min, "error_mm_max": err_max,
            "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
        })
    return out


def _build_method_ra_rows(record, rows):
    topic = record["topic"]
    method = None
    m = _RA_METHOD_FROM_TOPIC_RE.match(topic)
    if m:
        method = m.group(1)
    else:
        for kw in ("车端面", "外圆磨", "内外圆磨", "平面磨", "钻孔", "铰孔",
                   "切断", "螺纹加工", "铣端面", "圆柱铣刀铣削", "刨削",
                   "研磨", "车外圆"):
            if kw in topic:
                method = kw
                break
    method = method or record.get("subtype") or "?"
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        extras = {k: v for k, v in row.items()
                  if k not in {"stage", "material", "ra_min", "ra_max", "ra"}}
        out.append({
            "record_id": record["id"], "row_index": i,
            "method": method,
            "stage": row.get("stage"),
            "material": row.get("material"),
            "ra_min": row.get("ra_min"),
            "ra_max": row.get("ra_max"),
            "ra_text": row.get("ra"),
            "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
        })
    return out


def _build_surface_ra_rows(record, rows):
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        extras = {k: v for k, v in row.items()
                  if k not in {"surface", "condition", "ra", "ra_min", "ra_max"}}
        out.append({
            "record_id": record["id"], "row_index": i,
            "surface_kind": row.get("surface") or "?",
            "condition": row.get("condition"),
            "ra_text": row.get("ra"),
            "ra_min": row.get("ra_min"),
            "ra_max": row.get("ra_max"),
            "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
        })
    return out


def _build_cutting_rows(record, rows):
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        wp_text = row.get("workpiece_dim_text")
        wp_min, wp_max = parse_dim_range(wp_text) if wp_text else (None, None)
        if wp_min is None and wp_text:
            try:
                wp_min = wp_max = float(wp_text)
            except (TypeError, ValueError):
                pass
        ap_text = row.get("ap_segment")
        ap_min, ap_max = parse_dim_range(ap_text) if ap_text else (None, None)
        extras = {k: v for k, v in row.items() if k not in {
            "material", "tool_type", "tool", "tool_shank_mm", "operation",
            "workpiece_dim_text", "ap_segment",
            "f_min", "f_max", "vc_min_mps", "vc_max_mps",
            "n_min_rpm", "n_max_rpm",
            "ra_target_um", "kappa_prime_deg", "tool_nose_r_mm",
            "hardness_hbw", "heat_treat", "regime",
        }}
        if row.get("regime"):
            extras["regime"] = row["regime"]
        out.append({
            "record_id": record["id"], "row_index": i,
            "material": row.get("material"),
            "tool_type": row.get("tool") or row.get("tool_type"),
            "tool_shank_text": row.get("tool_shank_mm"),
            "operation": row.get("operation"),
            "workpiece_dim_text": wp_text,
            "workpiece_dim_min": wp_min, "workpiece_dim_max": wp_max,
            "ap_segment_text": ap_text,
            "ap_min": ap_min, "ap_max": ap_max,
            "f_min": row.get("f_min"), "f_max": row.get("f_max"),
            "vc_min_mps": row.get("vc_min_mps"),
            "vc_max_mps": row.get("vc_max_mps"),
            "n_min_rpm": row.get("n_min_rpm"),
            "n_max_rpm": row.get("n_max_rpm"),
            "ra_target_um": row.get("ra_target_um"),
            "kappa_prime_deg": (str(row["kappa_prime_deg"])
                                 if row.get("kappa_prime_deg") is not None else None),
            "tool_nose_r_mm": row.get("tool_nose_r_mm"),
            "hardness_hbw_text": row.get("hardness_hbw"),
            "heat_treat": row.get("heat_treat"),
            "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
        })
    return out


_INSERT_SQL = {
    "lookup_path_precision":
        "INSERT INTO lookup_path_precision "
        "(record_id, row_index, feature_kind, path_text, it_text, it_min, it_max, "
        " ra_min, ra_max, applies_to_solid, applies_to_preformed, extra_json) "
        "VALUES (:record_id,:row_index,:feature_kind,:path_text,:it_text,"
        " :it_min,:it_max,:ra_min,:ra_max,:applies_to_solid,:applies_to_preformed,"
        " :extra_json)",
    "lookup_method_economic_it":
        "INSERT INTO lookup_method_economic_it "
        "(record_id, row_index, method, feature, it_text, it_min, it_max, extra_json) "
        "VALUES (:record_id,:row_index,:method,:feature,:it_text,:it_min,:it_max,:extra_json)",
    "lookup_method_position_error":
        "INSERT INTO lookup_method_position_error "
        "(record_id, row_index, method, feature, error_text, error_mm_min, error_mm_max, extra_json) "
        "VALUES (:record_id,:row_index,:method,:feature,:error_text,:error_mm_min,"
        " :error_mm_max,:extra_json)",
    "lookup_method_ra":
        "INSERT INTO lookup_method_ra "
        "(record_id, row_index, method, stage, material, ra_min, ra_max, ra_text, extra_json) "
        "VALUES (:record_id,:row_index,:method,:stage,:material,:ra_min,:ra_max,"
        " :ra_text,:extra_json)",
    "lookup_surface_ra":
        "INSERT INTO lookup_surface_ra "
        "(record_id, row_index, surface_kind, condition, ra_text, ra_min, ra_max, extra_json) "
        "VALUES (:record_id,:row_index,:surface_kind,:condition,:ra_text,:ra_min,"
        " :ra_max,:extra_json)",
    "lookup_cutting_params":
        "INSERT INTO lookup_cutting_params "
        "(record_id, row_index, material, tool_type, tool_shank_text, operation, "
        " workpiece_dim_text, workpiece_dim_min, workpiece_dim_max, "
        " ap_segment_text, ap_min, ap_max, "
        " f_min, f_max, vc_min_mps, vc_max_mps, n_min_rpm, n_max_rpm, "
        " ra_target_um, kappa_prime_deg, tool_nose_r_mm, "
        " hardness_hbw_text, heat_treat, extra_json) "
        "VALUES (:record_id,:row_index,:material,:tool_type,:tool_shank_text,:operation,"
        " :workpiece_dim_text,:workpiece_dim_min,:workpiece_dim_max,"
        " :ap_segment_text,:ap_min,:ap_max,"
        " :f_min,:f_max,:vc_min_mps,:vc_max_mps,:n_min_rpm,:n_max_rpm,"
        " :ra_target_um,:kappa_prime_deg,:tool_nose_r_mm,"
        " :hardness_hbw_text,:heat_treat,:extra_json)",
}


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
    specialized_counts = {}

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

    # Second pass: dispatch each STD record to the specialized v2 lookup tables.
    # std_value_rows above is preserved for backward-compat with raw_sql in
    # pipeline-eval traces; lookup_* tables are the production query path.
    for record in seed:
        target_table, prepared_rows = _dispatch_specialized(record)
        if target_table is None or not prepared_rows:
            continue
        sql = _INSERT_SQL[target_table]
        cur.executemany(sql, prepared_rows)
        specialized_counts[target_table] = (
            specialized_counts.get(target_table, 0) + len(prepared_rows))

    conn.commit()
    conn.close()
    return {
        "db_path": str(db_path),
        "records_ingested": record_count,
        "value_rows_ingested": value_row_count,
        "index_records_no_value_table": index_record_count,
        "specialized_rows": specialized_counts,
    }


def main() -> int:
    report = ingest()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
