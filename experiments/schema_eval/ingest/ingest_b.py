"""Ingest seed_v1 + seed_cutting_v1 into schema_b (拆专表).

Uses framework_branch + record id heuristics to dispatch each record's
value_table rows to the appropriate specialized table.

Output: framework_seed_b.db
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parent.parent
SCHEMA = EXPERIMENT_ROOT / "schema" / "schema_b.sql"
SEED_DIR = REPO_ROOT / "experiments" / "framework_driven_seed" / "data"
DB_PATH = EXPERIMENT_ROOT / "framework_seed_b.db"


_RANGE_RE = re.compile(r"^\s*(-?[\d.]+)\s*[~\-至]\s*(-?[\d.]+)")
_IT_RANGE_RE = re.compile(r"^\s*(\d+)\s*[-~]\s*(\d+)")
_IT_SINGLE_RE = re.compile(r"^\s*(\d+)\s*$")


def parse_range(text):
    if text is None:
        return None, None
    m = _RANGE_RE.match(str(text))
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            return None, None
    return None, None


def parse_it_range(text):
    if text is None:
        return None, None
    m = _IT_RANGE_RE.match(str(text))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _IT_SINGLE_RE.match(str(text))
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def _collect_seeds():
    seed_v1 = json.loads((SEED_DIR / "seed_v1.json").read_text(encoding="utf-8"))
    extras = []
    for f in sorted(SEED_DIR.glob("seed_*.json")):
        if f.name == "seed_v1.json":
            continue
        extras.extend(json.loads(f.read_text(encoding="utf-8")))
    return seed_v1 + extras


# ---- per-pattern row builders ----


def build_path_row(record, row_index, row):
    """For records whose framework_branch starts with 2.3.2 and topic mentions 加工路线."""
    topic = record["topic"]
    feature_kind = (
        "外圆" if "外圆" in topic else
        "孔" if "孔" in topic else
        "平面" if "平面" in topic else None
    )
    path_text = row.get("path") or row.get("method") or ""
    it_text = row.get("IT") or row.get("it")
    it_min, it_max = parse_it_range(it_text) if it_text else (None, None)
    ra_min = ra_max = None
    if "ra_um" in row:
        ra_min, ra_max = parse_range(row["ra_um"])
    elif "ra_min" in row:
        ra_min, ra_max = row.get("ra_min"), row.get("ra_max")

    applies_solid = 1 if row.get("solid") else None
    applies_pre = 1 if row.get("preformed") else None

    extras = {k: v for k, v in row.items()
              if k not in {"path", "method", "IT", "it", "ra_um", "ra_min", "ra_max",
                           "solid", "preformed"}}
    return {
        "record_id": record["id"], "row_index": row_index,
        "feature_kind": feature_kind, "path_text": path_text,
        "it_text": it_text, "it_min": it_min, "it_max": it_max,
        "ra_min": ra_min, "ra_max": ra_max,
        "applies_to_solid": applies_solid, "applies_to_preformed": applies_pre,
        "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }


def build_method_econ_it_row(record, row_index, row):
    """For §2.8.1.4 records that are method × IT (no feature dim)."""
    it_text = row.get("IT") or row.get("it")
    it_min = row.get("IT_min")
    it_max = row.get("IT_max")
    if it_min is None and it_text:
        it_min, it_max = parse_it_range(it_text)
    extras = {k: v for k, v in row.items()
              if k not in {"method", "feature", "IT", "it", "IT_min", "IT_max"}}
    return {
        "record_id": record["id"], "row_index": row_index,
        "method": row.get("method") or row.get("path") or "?",
        "feature": row.get("feature"),
        "it_text": it_text,
        "it_min": int(it_min) if it_min is not None else None,
        "it_max": int(it_max) if it_max is not None else None,
        "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }


def build_method_position_error_row(record, row_index, row):
    err_text = row.get("error_mm") or row.get("error_text")
    err_min, err_max = parse_range(err_text) if err_text else (None, None)
    extras = {k: v for k, v in row.items()
              if k not in {"method", "feature", "error_mm", "error_text"}}
    return {
        "record_id": record["id"], "row_index": row_index,
        "method": row.get("method") or "?",
        "feature": row.get("feature"),
        "error_text": err_text, "error_mm_min": err_min, "error_mm_max": err_max,
        "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }


_RA_METHOD_FROM_TOPIC_RE = re.compile(r"^([一-鿿]+)\s+加工方法可达表面粗糙度")


def build_method_ra_row(record, row_index, row):
    # Method derived from record topic ("车端面 各级别可达 Ra")
    topic = record["topic"]
    method = None
    m = _RA_METHOD_FROM_TOPIC_RE.match(topic)
    if m:
        method = m.group(1)
    else:
        # subtype like 'ra_chart_face_turn' or topic contains "车端面 各级别"
        for kw in ("车端面", "外圆磨", "内外圆磨", "平面磨", "钻孔", "铰孔",
                   "切断", "螺纹加工", "铣端面", "圆柱铣刀铣削", "刨削",
                   "研磨", "车外圆"):
            if kw in topic:
                method = kw
                break
    method = method or record.get("subtype") or "?"
    extras = {k: v for k, v in row.items()
              if k not in {"stage", "material", "ra_min", "ra_max", "ra"}}
    return {
        "record_id": record["id"], "row_index": row_index,
        "method": method,
        "stage": row.get("stage"),
        "material": row.get("material"),
        "ra_min": row.get("ra_min"),
        "ra_max": row.get("ra_max"),
        "ra_text": row.get("ra"),
        "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }


def build_surface_ra_row(record, row_index, row):
    extras = {k: v for k, v in row.items()
              if k not in {"surface", "condition", "ra", "ra_min", "ra_max"}}
    ra_min = row.get("ra_min")
    ra_max = row.get("ra_max")
    return {
        "record_id": record["id"], "row_index": row_index,
        "surface_kind": row.get("surface") or "?",
        "condition": row.get("condition"),
        "ra_text": row.get("ra"),
        "ra_min": ra_min, "ra_max": ra_max,
        "extra_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }


def build_cutting_params_row(record, row_index, row):
    """§2.7 cutting params — 把所有维度尽量装进 typed columns."""
    workpiece_dim_text = row.get("workpiece_dim_text")
    wp_min, wp_max = parse_range(workpiece_dim_text) if workpiece_dim_text else (None, None)
    if wp_min is None and workpiece_dim_text:
        # try single number
        try:
            wp_min = wp_max = float(workpiece_dim_text)
        except (TypeError, ValueError):
            pass

    ap_text = row.get("ap_segment")
    ap_min, ap_max = parse_range(ap_text) if ap_text else (None, None)

    extras = {k: v for k, v in row.items() if k not in {
        "material", "tool_type", "tool_shank_mm", "operation",
        "workpiece_dim_text", "ap_segment",
        "f_min", "f_max", "vc_min_mps", "vc_max_mps", "n_min_rpm", "n_max_rpm",
        "ra_target_um", "kappa_prime_deg", "tool_nose_r_mm",
        "hardness_hbw", "heat_treat", "regime", "tool",
    }}
    return {
        "record_id": record["id"], "row_index": row_index,
        "material": row.get("material"),
        "tool_type": row.get("tool") or row.get("tool_type"),
        "tool_shank_text": row.get("tool_shank_mm"),
        "operation": row.get("operation"),
        "workpiece_dim_text": workpiece_dim_text,
        "workpiece_dim_min": wp_min,
        "workpiece_dim_max": wp_max,
        "ap_segment_text": ap_text,
        "ap_min": ap_min, "ap_max": ap_max,
        "f_min": row.get("f_min"), "f_max": row.get("f_max"),
        "vc_min_mps": row.get("vc_min_mps"), "vc_max_mps": row.get("vc_max_mps"),
        "n_min_rpm": row.get("n_min_rpm"), "n_max_rpm": row.get("n_max_rpm"),
        "ra_target_um": row.get("ra_target_um"),
        "kappa_prime_deg": str(row.get("kappa_prime_deg")) if row.get("kappa_prime_deg") is not None else None,
        "tool_nose_r_mm": row.get("tool_nose_r_mm"),
        "hardness_hbw_text": row.get("hardness_hbw"),
        "heat_treat": row.get("heat_treat"),
        "extra_json": json.dumps({**extras, "regime": row.get("regime")}, ensure_ascii=False)
                      if (extras or row.get("regime")) else None,
    }


# ---- record dispatcher ----


def dispatch_record(record):
    """Return ('table_name', [row_dicts]) or ('payload_only', []) for unstructured."""
    branch = record["framework_branch"]
    rid = record["id"]
    payload = record.get("payload") or {}
    value_table = payload.get("value_table") or []
    size_segments = payload.get("size_segments")  # legacy

    if record["family"] != "标准":
        return None, []  # EXP/CALC/CASE 都不进任何 lookup table
    if not value_table and not size_segments:
        return "index_only", []  # 占位记录

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

    # Choose target table
    if branch.startswith("2.3.2") and "PATH" in rid:
        table = "lookup_path_precision"
        builder = build_path_row
    elif rid == "STD-2.3.2-METHOD-ERRORS-001":
        table = "lookup_method_position_error"
        builder = build_method_position_error_row
    elif branch.startswith("2.8.1.4") and "POS-ECON" in rid:
        # PARALLEL-HOLE-POS / PERP-HOLE-POS — error_mm shape
        table = "lookup_method_position_error"
        builder = build_method_position_error_row
    elif branch.startswith("2.8.1.4"):
        table = "lookup_method_economic_it"
        builder = build_method_econ_it_row
    elif branch.startswith("2.8.2.1"):
        table = "lookup_method_ra"
        builder = build_method_ra_row
    elif branch.startswith("2.8.2.4"):
        table = "lookup_surface_ra"
        builder = build_surface_ra_row
    elif branch.startswith("2.7"):
        table = "lookup_cutting_params"
        builder = build_cutting_params_row
    else:
        # Specialized records (2.4.4 thread / 2.8.3 hardening / etc) → payload only
        return "payload_only", []

    built = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        try:
            built.append(builder(record, i, r))
        except Exception as e:
            print(f"[warn] failed to build {rid} row {i}: {e}", file=sys.stderr)
    return table, built


# ---- INSERT helpers ----

INSERT_SQL = {
    "lookup_path_precision": """
        INSERT INTO lookup_path_precision
          (record_id, row_index, feature_kind, path_text, it_text, it_min, it_max,
           ra_min, ra_max, applies_to_solid, applies_to_preformed, extra_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
    "lookup_method_economic_it": """
        INSERT INTO lookup_method_economic_it
          (record_id, row_index, method, feature, it_text, it_min, it_max, extra_json)
        VALUES (?,?,?,?,?,?,?,?)""",
    "lookup_method_position_error": """
        INSERT INTO lookup_method_position_error
          (record_id, row_index, method, feature, error_text, error_mm_min, error_mm_max, extra_json)
        VALUES (?,?,?,?,?,?,?,?)""",
    "lookup_method_ra": """
        INSERT INTO lookup_method_ra
          (record_id, row_index, method, stage, material, ra_min, ra_max, ra_text, extra_json)
        VALUES (?,?,?,?,?,?,?,?,?)""",
    "lookup_surface_ra": """
        INSERT INTO lookup_surface_ra
          (record_id, row_index, surface_kind, condition, ra_text, ra_min, ra_max, extra_json)
        VALUES (?,?,?,?,?,?,?,?)""",
    "lookup_cutting_params": """
        INSERT INTO lookup_cutting_params
          (record_id, row_index, material, tool_type, tool_shank_text, operation,
           workpiece_dim_text, workpiece_dim_min, workpiece_dim_max,
           ap_segment_text, ap_min, ap_max,
           f_min, f_max, vc_min_mps, vc_max_mps, n_min_rpm, n_max_rpm,
           ra_target_um, kappa_prime_deg, tool_nose_r_mm,
           hardness_hbw_text, heat_treat, extra_json)
        VALUES (?,?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?,?,?, ?,?,?, ?,?,?)""",
}

INSERT_FIELD_ORDER = {
    "lookup_path_precision": [
        "record_id","row_index","feature_kind","path_text","it_text","it_min","it_max",
        "ra_min","ra_max","applies_to_solid","applies_to_preformed","extra_json"],
    "lookup_method_economic_it": [
        "record_id","row_index","method","feature","it_text","it_min","it_max","extra_json"],
    "lookup_method_position_error": [
        "record_id","row_index","method","feature","error_text","error_mm_min","error_mm_max","extra_json"],
    "lookup_method_ra": [
        "record_id","row_index","method","stage","material","ra_min","ra_max","ra_text","extra_json"],
    "lookup_surface_ra": [
        "record_id","row_index","surface_kind","condition","ra_text","ra_min","ra_max","extra_json"],
    "lookup_cutting_params": [
        "record_id","row_index","material","tool_type","tool_shank_text","operation",
        "workpiece_dim_text","workpiece_dim_min","workpiece_dim_max",
        "ap_segment_text","ap_min","ap_max",
        "f_min","f_max","vc_min_mps","vc_max_mps","n_min_rpm","n_max_rpm",
        "ra_target_um","kappa_prime_deg","tool_nose_r_mm",
        "hardness_hbw_text","heat_treat","extra_json"],
}


def ingest():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    cur = conn.cursor()

    seed = _collect_seeds()

    # Insert kb_records (same as schema_a)
    rec_count = 0
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
        rec_count += 1

    # Dispatch each record to its specialized table
    by_table = {}
    payload_only = 0
    index_only = 0
    for record in seed:
        table, rows = dispatch_record(record)
        if table is None:
            continue
        if table == "payload_only":
            payload_only += 1
            continue
        if table == "index_only":
            index_only += 1
            continue
        for row in rows:
            tup = tuple(row.get(f) for f in INSERT_FIELD_ORDER[table])
            cur.execute(INSERT_SQL[table], tup)
            by_table.setdefault(table, 0)
            by_table[table] += 1

    conn.commit()
    conn.close()
    return {
        "db_path": str(DB_PATH),
        "records_ingested": rec_count,
        "rows_by_table": by_table,
        "payload_only_records": payload_only,
        "index_only_records": index_only,
    }


def main():
    report = ingest()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
