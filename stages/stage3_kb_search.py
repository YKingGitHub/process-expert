"""
Stage 3: Knowledge Base Search — 本地 SQLite 知识库检索

三路查询:
1. process_params — 材料匹配的切削参数
2. experience_log — 工艺经验 Top 20
3. kb_chunks (FTS5) — 手册全文检索（金属切削工艺技术手册 + 车削工艺手册）
"""

import logging
import sqlite3
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Default knowledge DB path (relative to this file's directory)
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "knowledge.db"


def _connect(config: dict) -> sqlite3.Connection:
    """Connect to the local SQLite knowledge database."""
    db_path = config.get("database", {}).get("path", str(DEFAULT_DB_PATH))
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Knowledge database not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _query_params(conn: sqlite3.Connection, material: str, tracer) -> dict:
    """Query process_params for material-matching parameters."""
    sql = """
        SELECT material_grade, operation_type, parameter_name,
               parameter_value, parameter_unit, equipment, surface_finish
        FROM process_params
        WHERE material_grade LIKE ? OR material_grade = ?
        ORDER BY operation_type, parameter_name
    """
    like_pattern = f"%{material}%"
    tracer.log_reasoning(
        f"Querying process_params for material LIKE '%{material}%'"
    )

    cur = conn.execute(sql, (like_pattern, material))
    rows = [dict(r) for r in cur.fetchall()]

    tracer.log_search_result(
        source="SQLite / process_params",
        query=f"material_grade LIKE '%{material}%'",
        results_summary=f"{len(rows)} rows",
    )

    # Group by operation_type
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        op_type = row.get("operation_type", "unknown")
        grouped[op_type].append(row)

    return dict(grouped)


def _query_experiences(conn: sqlite3.Connection, tracer) -> list[dict]:
    """Query experience_log for top process-domain experiences."""
    sql = """
        SELECT category, situation, action_taken, outcome, lesson
        FROM experience_log
        WHERE expert_domain = 'process'
        ORDER BY confidence DESC
        LIMIT 20
    """
    tracer.log_reasoning(
        "Querying experience_log for top 20 process-domain experiences"
    )

    cur = conn.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]

    tracer.log_search_result(
        source="SQLite / experience_log",
        query="expert_domain = 'process' ORDER BY confidence DESC LIMIT 20",
        results_summary=f"{len(rows)} rows",
    )
    return rows


def _query_chunks_fts(
    conn: sqlite3.Connection,
    material: str,
    operation_types: list[str],
    tracer,
) -> list[dict]:
    """Full-text search on kb_chunks for relevant manual excerpts."""
    # Build search terms: material + operation types
    search_terms = [material]
    for op in operation_types:
        # Strip common suffixes to broaden search
        clean = op.replace("/", " ").replace("标识", "").strip()
        if clean and clean not in ("领料", "入库", "无"):
            search_terms.append(clean)

    if not search_terms:
        return []

    # FTS5 query: OR-join all terms
    fts_query = " OR ".join(search_terms)
    tracer.log_reasoning(
        f"FTS5 search on kb_chunks: '{fts_query}'"
    )

    try:
        sql = """
            SELECT c.content, c.source_file,
                   rank
            FROM kb_chunks_fts fts
            JOIN kb_chunks c ON c.rowid = fts.rowid
            WHERE kb_chunks_fts MATCH ?
            ORDER BY rank
            LIMIT 15
        """
        cur = conn.execute(sql, (fts_query,))
        rows = [dict(r) for r in cur.fetchall()]

        tracer.log_search_result(
            source="SQLite / kb_chunks (FTS5)",
            query=fts_query,
            results_summary=f"{len(rows)} chunks matched",
        )
        return rows

    except Exception as exc:
        tracer.log_reasoning(f"FTS5 search failed: {exc}, trying LIKE fallback")

        # Fallback: simple LIKE search
        like_results = []
        for term in search_terms[:3]:
            sql = """
                SELECT content, source_file
                FROM kb_chunks
                WHERE content LIKE ?
                LIMIT 5
            """
            cur = conn.execute(sql, (f"%{term}%",))
            like_results.extend([dict(r) for r in cur.fetchall()])

        tracer.log_search_result(
            source="SQLite / kb_chunks (LIKE fallback)",
            query=f"LIKE search for {search_terms[:3]}",
            results_summary=f"{len(like_results)} chunks matched",
        )
        return like_results[:15]


def search_knowledge_base(
    material: str,
    operation_types: list[str],
    config: dict,
    tracer,
) -> dict:
    """
    Query the local knowledge base (SQLite) for machining parameters,
    expert experience, and manual excerpts.

    Returns:
        dict with keys:
            params — dict grouped by operation_type
            experiences — list of experience dicts
            manual_excerpts — list of relevant manual chunks
    """
    tracer.begin_stage(
        "Stage 3: Knowledge Base Search",
        input_data={
            "material": material,
            "operation_types": operation_types,
        },
    )

    result: dict = {
        "params": {},
        "experiences": [],
        "manual_excerpts": [],
    }

    try:
        conn = _connect(config)
    except Exception as exc:
        error_msg = f"Knowledge DB connection failed: {exc}"
        logger.error(error_msg)
        tracer.log_error(error_msg)
        tracer.end_stage(output_data=result)
        return result

    try:
        # Query 1: process_params
        result["params"] = _query_params(conn, material, tracer)

        # Query 2: experience_log
        result["experiences"] = _query_experiences(conn, tracer)

        # Query 3: manual chunks (FTS5 full-text search)
        result["manual_excerpts"] = _query_chunks_fts(
            conn, material, operation_types, tracer
        )

    except Exception as exc:
        error_msg = f"Knowledge base query failed: {exc}"
        logger.error(error_msg)
        tracer.log_error(error_msg)
    finally:
        conn.close()

    # Build output summary
    param_summary = {
        op: len(items) for op, items in result["params"].items()
    }
    output_summary = {
        "params_by_operation": param_summary,
        "total_param_rows": sum(param_summary.values()),
        "experience_count": len(result["experiences"]),
        "manual_excerpt_count": len(result["manual_excerpts"]),
    }
    tracer.end_stage(output_data=output_summary)

    return result
