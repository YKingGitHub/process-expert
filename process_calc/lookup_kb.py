"""Knowledge-base lookups against the framework_driven_seed SQLite DB.

These methods are *retrievals* (not closed-form calculations): they query
``framework_seed.db`` for textbook-table rows that match a method or feature
description, then package the rows into the uniform ``build_result`` shape
so callers can render them alongside calculated answers.

**Schema v2 (since 2026-05-09)**: queries hit specialized lookup tables
(``lookup_path_precision`` / ``lookup_method_economic_it`` /
``lookup_method_position_error`` / ``lookup_method_ra`` /
``lookup_surface_ra`` / ``lookup_cutting_params`` / ``lookup_size_method_grid``)
chosen by the schema A/B/C experiment (see Projects/process-expert/designs/
2026-05-09-01-schema-restructure-experiment/). std_value_rows is still
ingested for backward compat with raw_sql in pipeline-eval traces; this
module no longer queries it.

The DB path defaults to ``experiments/framework_driven_seed/sqlite/
framework_seed.db`` under the repo root, but can be overridden via the
``PROCESS_CALC_KB_DB`` env var or by passing ``db_path=`` explicitly.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from process_calc.errors import InputOutOfRangeError, MissingParameterError
from process_calc.result import build_result


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _REPO_ROOT / "experiments" / "framework_driven_seed" / "sqlite" / "framework_seed.db"


def _resolve_db_path(db_path: str | Path | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    env = os.environ.get("PROCESS_CALC_KB_DB")
    if env:
        return Path(env)
    return _DEFAULT_DB


def _connect(db_path: str | Path | None) -> sqlite3.Connection:
    p = _resolve_db_path(db_path)
    if not p.exists():
        raise InputOutOfRangeError(
            f"KB SQLite DB not found at {p}. Run experiments/framework_driven_seed/"
            f"sqlite/ingest.py first, or set PROCESS_CALC_KB_DB."
        )
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def lookup_economic_precision(
    method: str | None = None,
    feature: str | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Look up economic-precision IT for a machining method.

    Source: ``lookup_method_economic_it`` (§2.8.1.4 records). At least one of
    ``method`` or ``feature`` must be given.
    """
    if not method and not feature:
        raise MissingParameterError(
            "lookup_economic_precision requires at least one of method= or feature="
        )
    where = ["it_text IS NOT NULL"]
    params: list[Any] = []
    if method:
        where.append("method LIKE ?")
        params.append(f"%{method}%")
    if feature:
        where.append("feature LIKE ?")
        params.append(f"%{feature}%")
    sql = f"""
        SELECT record_id, method, feature, it_text AS it, it_min, it_max
        FROM lookup_method_economic_it
        WHERE {' AND '.join(where)}
        ORDER BY record_id, row_index
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    steps = [
        "Query lookup_method_economic_it (specialized v2 table for §2.8.1.4)",
        f"Apply method substring filter: {method!r}" if method else "method filter: (none)",
        f"Apply feature substring filter: {feature!r}" if feature else "feature filter: (none)",
        f"Found {len(rows)} matching row(s)",
    ]
    return build_result(
        method_id="lookup_economic_precision",
        result={"matches": rows, "match_count": len(rows)},
        unit="IT-grade",
        steps=steps,
        formula="SELECT method, feature, it_text, it_min, it_max "
                "FROM lookup_method_economic_it WHERE it_text IS NOT NULL",
        verified=True,
    )


def lookup_path_precision(
    path_keyword: str,
    feature: str | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Look up the IT/Ra band achievable by a process route (加工路线).

    Source: ``lookup_path_precision`` (specialized table for §2.3.2 PATH
    records). ``path_keyword`` matches against ``path_text``. ``feature``
    is one of '外圆' / '孔' / '平面' (matches feature_kind exactly).
    """
    if not path_keyword:
        raise MissingParameterError("lookup_path_precision requires path_keyword=")
    where = ["path_text LIKE ?"]
    params: list[Any] = [f"%{path_keyword}%"]
    if feature:
        # feature_kind is one of '外圆'/'孔'/'平面' — exact match on these
        where.append("feature_kind = ?")
        params.append(feature)
    sql = f"""
        SELECT record_id, row_index, feature_kind, path_text,
               it_text AS it, it_min, it_max, ra_min, ra_max
        FROM lookup_path_precision
        WHERE {' AND '.join(where)}
        ORDER BY record_id, row_index
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    # Add 'method' alias for backward-compat with old caller expectations
    for r in rows:
        r["method"] = r.get("path_text")

    steps = [
        f"Query lookup_path_precision for path LIKE %{path_keyword}%",
        f"feature_kind filter: {feature!r}" if feature else "feature filter: (none)",
        f"Found {len(rows)} matching path row(s)",
    ]
    return build_result(
        method_id="lookup_path_precision",
        result={"matches": rows, "match_count": len(rows)},
        unit="IT/Ra",
        steps=steps,
        formula="SELECT path_text, it_*, ra_* FROM lookup_path_precision "
                "WHERE path_text LIKE ?",
        verified=True,
    )


def lookup_method_position_error(
    feature: str,
    db_path: str | Path | None = None,
) -> dict:
    """Look up positional error (mm range) achievable by alternative methods.

    Source: ``lookup_method_position_error`` (specialized table for METHOD-ERRORS
    + PARALLEL-HOLE-POS + PERP-HOLE-POS records).
    """
    if not feature:
        raise MissingParameterError("lookup_method_position_error requires feature=")
    sql = """
        SELECT record_id, method, feature, error_text, error_mm_min, error_mm_max
        FROM lookup_method_position_error
        WHERE feature LIKE ?
        ORDER BY error_mm_min
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, [f"%{feature}%"]).fetchall()]

    steps = [
        f"Query lookup_method_position_error for feature LIKE %{feature}%",
        "Sort ascending by best-case error (error_mm_min)",
        f"Found {len(rows)} method(s); best error = "
        + (f"{rows[0]['error_text']}" if rows else "—"),
    ]
    return build_result(
        method_id="lookup_method_position_error",
        result={"matches": rows, "match_count": len(rows)},
        unit="mm",
        steps=steps,
        formula="SELECT method, error_mm_min, error_mm_max "
                "FROM lookup_method_position_error WHERE feature LIKE ?",
        verified=True,
    )


def lookup_machining_allowance(
    feature_kind: str | None = None,
    operation: str | None = None,
    size_mm: float | None = None,
    length_mm: float | None = None,
    material: str | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Look up machining allowance recommendations.

    Source: ``lookup_machining_allowance`` (specialized table for §2.9.1
    Ch6 余量表 from 金属切削工艺技术手册). All filters typed.

    Selection rules:
      - feature_kind: '外圆' / '孔' / '端面' / '切断' (exact match)
      - operation: '粗车' / '半精车' / '精车' / '磨' / '钻' / '切断' / ... (LIKE)
      - size_mm: filter rows where size_min <= size_mm <= size_max (or unbounded)
      - length_mm: same for length_min/length_max
      - material: LIKE filter (mostly for 切断 table)
    """
    if not any([feature_kind, operation, size_mm, length_mm, material]):
        raise MissingParameterError(
            "lookup_machining_allowance requires at least one of: "
            "feature_kind, operation, size_mm, length_mm, material"
        )
    where = ["1=1"]
    params: list[Any] = []
    if feature_kind:
        where.append("feature_kind = ?")
        params.append(feature_kind)
    if operation:
        where.append("operation LIKE ?")
        params.append(f"%{operation}%")
    if material:
        where.append("material LIKE ?")
        params.append(f"%{material}%")
    if size_mm is not None:
        where.append("(size_min IS NULL OR size_min <= ?) "
                     "AND (size_max IS NULL OR size_max >= ?)")
        params.extend([size_mm, size_mm])
    if length_mm is not None:
        where.append("(length_min IS NULL OR length_min <= ?) "
                     "AND (length_max IS NULL OR length_max >= ?)")
        params.extend([length_mm, length_mm])
    sql = f"""
        SELECT record_id, row_index, feature_kind, operation, material,
               size_segment_text, length_segment_text, heat_treat,
               allowance_text, allowance_mm_min, allowance_mm_max, extra_json
        FROM lookup_machining_allowance
        WHERE {' AND '.join(where)}
        ORDER BY record_id, row_index
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    steps = [
        "Query lookup_machining_allowance (specialized v2 table for §2.9.1)",
        f"feature_kind: {feature_kind!r}" if feature_kind else "feature: (any)",
        f"operation filter: {operation!r}" if operation else "operation: (any)",
        f"size_mm: {size_mm}" if size_mm is not None else "size: (any)",
        f"length_mm: {length_mm}" if length_mm is not None else "length: (any)",
        f"Found {len(rows)} allowance row(s)",
    ]
    return build_result(
        method_id="lookup_machining_allowance",
        result={"matches": rows, "match_count": len(rows)},
        unit="mm",
        steps=steps,
        formula="SELECT feature_kind, operation, allowance_mm_min/max "
                "FROM lookup_machining_allowance WHERE typed-column filters",
        verified=True,
    )


def lookup_cutting_params(
    material: str | None = None,
    operation: str | None = None,
    workpiece_dim_text: str | None = None,
    ra_target_um: float | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Look up cutting parameters (vc / f / n / ap) for turning operations.

    Source: ``lookup_cutting_params`` (specialized table for §2.7 cutting
    parameters from 车削工艺手册). All filters are typed columns —
    no JSON extract needed.
    """
    if not any([material, operation, workpiece_dim_text, ra_target_um]):
        raise MissingParameterError(
            "lookup_cutting_params requires at least one of: material, "
            "operation, workpiece_dim_text, ra_target_um"
        )
    where = ["1=1"]
    params: list[Any] = []
    if material:
        where.append("material LIKE ?")
        params.append(f"%{material}%")
    if operation:
        where.append("operation LIKE ?")
        params.append(f"%{operation}%")
    if workpiece_dim_text:
        where.append("workpiece_dim_text = ?")
        params.append(workpiece_dim_text)
    if ra_target_um is not None:
        where.append("ra_target_um = ?")
        params.append(ra_target_um)
    sql = f"""
        SELECT record_id, row_index, material, tool_type, tool_shank_text,
               operation, workpiece_dim_text, ap_segment_text,
               f_min, f_max, vc_min_mps, vc_max_mps,
               n_min_rpm, n_max_rpm, ra_target_um,
               kappa_prime_deg, tool_nose_r_mm,
               hardness_hbw_text, heat_treat
        FROM lookup_cutting_params
        WHERE {' AND '.join(where)}
        ORDER BY record_id, row_index
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    steps = [
        "Query lookup_cutting_params (specialized v2 table for §2.7)",
        f"material filter: {material!r}" if material else "material: (any)",
        f"operation filter: {operation!r}" if operation else "operation: (any)",
        f"workpiece_dim_text: {workpiece_dim_text!r}" if workpiece_dim_text else "dim: (any)",
        f"ra_target_um: {ra_target_um!r}" if ra_target_um is not None else "ra: (any)",
        f"Found {len(rows)} cutting-param row(s)",
    ]
    return build_result(
        method_id="lookup_cutting_params",
        result={"matches": rows, "match_count": len(rows)},
        unit="vc(m/s) / f(mm/r) / n(r/min)",
        steps=steps,
        formula="SELECT material, operation, workpiece_dim_text, "
                "f_min/max, vc_min/max, n_min/max, ... "
                "FROM lookup_cutting_params WHERE typed-column filters",
        verified=True,
    )
