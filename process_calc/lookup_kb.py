"""Knowledge-base lookups against the framework_driven_seed SQLite DB.

These methods are *retrievals* (not closed-form calculations): they query
``framework_seed.db`` for textbook-table rows that match a method or feature
description, then package the rows into the uniform ``build_result`` shape
so callers can render them alongside calculated answers.

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

    Source: framework branch §2.8.1.4 records (e.g. ``STD-2.8.1.4-METHOD-IT-CHART-001``,
    ``STD-2.8.1.4-DEEP-HOLE-ECON-001``). At least one of ``method`` or ``feature``
    must be given. Matching is case-insensitive substring on Chinese terms.

    Returns rows shaped ``{record_id, method, feature, it, it_min, it_max,
    source_doc, source_page}`` ranked by record_id.
    """
    if not method and not feature:
        raise MissingParameterError(
            "lookup_economic_precision requires at least one of method= or feature="
        )
    where = ["framework_branch LIKE '2.8.1.4%'", "it IS NOT NULL"]
    params: list[Any] = []
    if method:
        where.append("method LIKE ?")
        params.append(f"%{method}%")
    if feature:
        where.append("(feature LIKE ? OR topic LIKE ?)")
        params.append(f"%{feature}%")
        params.append(f"%{feature}%")
    sql = f"""
        SELECT record_id, method, feature, it, it_min, it_max,
               source_page, topic
        FROM v_std_lookup
        WHERE {' AND '.join(where)}
        ORDER BY record_id, row_index
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    steps = [
        f"Filter STD records under framework_branch §2.8.1.4 where it IS NOT NULL",
        f"Apply method substring filter: {method!r}" if method else "method filter: (none)",
        f"Apply feature/topic substring filter: {feature!r}" if feature else "feature filter: (none)",
        f"Found {len(rows)} matching row(s)",
    ]
    return build_result(
        method_id="lookup_economic_precision",
        result={"matches": rows, "match_count": len(rows)},
        unit="IT-grade",
        steps=steps,
        formula="SELECT … FROM v_std_lookup WHERE framework_branch LIKE '2.8.1.4%' AND it IS NOT NULL",
        verified=True,
    )


def lookup_path_precision(
    path_keyword: str,
    feature: str | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Look up the IT/Ra band achievable by a process route (加工路线).

    Source: framework branch §2.3.2 PATH records (外圆/孔/平面 process-route
    tables, e.g. ``STD-2.3.2-OUTER-CYL-PATH-001``). The ``path_keyword`` is
    matched as a substring against the ``method`` column (which stores the
    whole route, e.g. "粗车→半精车→精车").

    ``feature`` can narrow to outer-cyl / hole / plane via topic filter.
    """
    if not path_keyword:
        raise MissingParameterError("lookup_path_precision requires path_keyword=")
    where = [
        "framework_branch LIKE '2.3.2%'",
        "method LIKE ?",
        "(it IS NOT NULL OR ra_min IS NOT NULL)",
    ]
    params: list[Any] = [f"%{path_keyword}%"]
    if feature:
        where.append("topic LIKE ?")
        params.append(f"%{feature}%")
    sql = f"""
        SELECT record_id, method, it, it_min, it_max, ra_min, ra_max,
               source_page, topic
        FROM v_std_lookup
        WHERE {' AND '.join(where)}
        ORDER BY record_id, row_index
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    steps = [
        f"Filter §2.3.2 PATH records by method LIKE %{path_keyword}%",
        f"Optional feature filter: {feature!r}" if feature else "feature filter: (none)",
        f"Found {len(rows)} matching path row(s)",
    ]
    return build_result(
        method_id="lookup_path_precision",
        result={"matches": rows, "match_count": len(rows)},
        unit="IT/Ra",
        steps=steps,
        formula="SELECT … FROM v_std_lookup WHERE framework_branch LIKE '2.3.2%' AND method LIKE ?",
        verified=True,
    )


def lookup_method_position_error(
    feature: str,
    db_path: str | Path | None = None,
) -> dict:
    """Look up positional error (mm range) achievable by alternative methods.

    Source: ``STD-2.3.2-METHOD-ERRORS-001`` (机械加工方法可达定位精度对照表).
    Returns rows shaped ``{method, feature, error_text, error_mm_min,
    error_mm_max}`` for the given feature description (substring match).
    """
    if not feature:
        raise MissingParameterError("lookup_method_position_error requires feature=")
    sql = """
        SELECT record_id, method, feature, error_text, error_mm_min, error_mm_max,
               source_page
        FROM v_std_lookup
        WHERE record_id = 'STD-2.3.2-METHOD-ERRORS-001'
          AND feature LIKE ?
        ORDER BY error_mm_min
    """
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, [f"%{feature}%"]).fetchall()]

    steps = [
        f"Query STD-2.3.2-METHOD-ERRORS-001 for feature LIKE %{feature}%",
        f"Sort ascending by best-case error (error_mm_min)",
        f"Found {len(rows)} method(s); best error = "
        + (f"{rows[0]['error_text']}" if rows else "—"),
    ]
    return build_result(
        method_id="lookup_method_position_error",
        result={"matches": rows, "match_count": len(rows)},
        unit="mm",
        steps=steps,
        formula="SELECT method, error_mm_min, error_mm_max FROM v_std_lookup "
                "WHERE record_id='STD-2.3.2-METHOD-ERRORS-001' AND feature LIKE ?",
        verified=True,
    )
