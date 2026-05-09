"""Ingest seed_v1 + seed_cutting_v1 into schema_c (EAV).

Each value_table row → N attribute tuples. For numeric values both
attr_value_text (string mirror) and attr_value_num are filled.

Output: framework_seed_c.db
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parent.parent
SCHEMA = EXPERIMENT_ROOT / "schema" / "schema_c.sql"
SEED_DIR = REPO_ROOT / "experiments" / "framework_driven_seed" / "data"
DB_PATH = EXPERIMENT_ROOT / "framework_seed_c.db"


def _collect_seeds():
    seed_v1 = json.loads((SEED_DIR / "seed_v1.json").read_text(encoding="utf-8"))
    extras = []
    for f in sorted(SEED_DIR.glob("seed_*.json")):
        if f.name == "seed_v1.json":
            continue
        extras.extend(json.loads(f.read_text(encoding="utf-8")))
    return seed_v1 + extras


def _is_numeric(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def _emit_attr_tuples(record_id, row_index, key, value, unit=None):
    """Yield (record_id, row_index, attr_key, attr_value_text, attr_value_num, attr_unit)."""
    if value is None:
        return
    if isinstance(value, (list, dict)):
        # Skip nested for EAV; recursion would explode. Store as JSON-stringified.
        yield (record_id, row_index, key, json.dumps(value, ensure_ascii=False), None, unit)
        return
    text = str(value)
    num = float(value) if _is_numeric(value) else None
    yield (record_id, row_index, key, text, num, unit)


def _flatten_row(record, row_index, row):
    """Convert a single value_table row dict into attr tuples."""
    rid = record["id"]
    tuples = []
    for k, v in row.items():
        # Pick a unit hint by key name
        unit = None
        if k in {"ra_min", "ra_max", "ra_target_um"}:
            unit = "μm"
        elif k in {"f_min", "f_max"}:
            unit = "mm/r"
        elif k in {"vc_min_mps", "vc_max_mps"}:
            unit = "m/s"
        elif k in {"n_min_rpm", "n_max_rpm"}:
            unit = "r/min"
        elif k in {"ap_min", "ap_max", "workpiece_dim_min", "workpiece_dim_max",
                    "error_mm_min", "error_mm_max"}:
            unit = "mm"
        elif k in {"deviation_um"}:
            unit = "μm"
        elif k in {"tool_nose_r_mm"}:
            unit = "mm"
        for t in _emit_attr_tuples(rid, row_index, k, v, unit):
            tuples.append(t)
    return tuples


def _expand_methods_array(value_table):
    """Same expansion as schema_a/b: nested methods[] array → multiple rows."""
    rows = []
    for vrow in value_table:
        if isinstance(vrow, dict) and isinstance(vrow.get("methods"), list):
            parent = {k: v for k, v in vrow.items() if k != "methods"}
            for inner in vrow["methods"]:
                if isinstance(inner, dict):
                    rows.append({**parent, **inner})
        else:
            rows.append(vrow)
    return rows


def ingest():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    cur = conn.cursor()

    seed = _collect_seeds()
    rec_count = 0
    attr_count = 0

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

        if record["family"] != "标准":
            continue

        payload = record.get("payload") or {}
        rows = _expand_methods_array(payload.get("value_table") or [])
        if payload.get("size_segments"):
            for seg in payload["size_segments"]:
                rows.append({**seg, "method": payload.get("standard"),
                             "method_group": payload.get("kind")})

        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            tuples = _flatten_row(record, i, row)
            cur.executemany(
                """
                INSERT INTO std_attributes
                  (record_id, row_index, attr_key, attr_value_text, attr_value_num, attr_unit)
                VALUES (?,?,?,?,?,?)
                """,
                tuples,
            )
            attr_count += len(tuples)

    conn.commit()
    conn.close()
    return {
        "db_path": str(DB_PATH),
        "records_ingested": rec_count,
        "attribute_tuples": attr_count,
    }


def main():
    report = ingest()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
