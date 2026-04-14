"""Database writer — writes extracted records to SQLite."""

import sqlite3
from datetime import datetime

from ingest.schemas import KnowledgeChunk, ProcessParam

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS process_params (
    id INTEGER PRIMARY KEY,
    material_grade TEXT NOT NULL DEFAULT '',
    material_category TEXT DEFAULT '',
    operation_type TEXT NOT NULL DEFAULT '',
    parameter_name TEXT NOT NULL DEFAULT '',
    parameter_value TEXT NOT NULL DEFAULT '',
    parameter_unit TEXT DEFAULT '',
    equipment TEXT DEFAULT '',
    surface_finish TEXT DEFAULT '',
    tolerance TEXT DEFAULT '',
    conditions TEXT DEFAULT '',
    source_doc TEXT DEFAULT '',
    confidence REAL DEFAULT 0.5,
    chapter TEXT DEFAULT '',
    table_ref TEXT DEFAULT '',
    source_page INTEGER DEFAULT 0,
    extraction_method TEXT DEFAULT 'llm_extracted',
    cross_validated INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS kb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source_file TEXT DEFAULT '',
    domain TEXT DEFAULT 'process',
    doc_type TEXT DEFAULT 'manual',
    chapter_title TEXT DEFAULT '',
    page_start INTEGER DEFAULT 0,
    page_end INTEGER DEFAULT 0,
    source_page INTEGER NOT NULL DEFAULT 0,
    chapter TEXT DEFAULT '',
    source TEXT DEFAULT '',
    created_at TEXT DEFAULT NULL
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't already exist."""
    conn.executescript(_INIT_SQL)
    conn.commit()


def write_params(db_path: str, params: list[ProcessParam]) -> tuple[int, int]:
    """写入参数到 process_params。返回 (inserted, skipped)。"""
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = skipped = 0
    for p in params:
        # 先检查是否已存在（利用唯一索引字段）
        exists = conn.execute(
            "SELECT 1 FROM process_params WHERE table_ref=? AND source_page=? "
            "AND operation_type=? AND material_grade=? AND parameter_name=? LIMIT 1",
            (p.table_ref, p.source_page, p.operation_type, p.material_grade, p.parameter_name)
        ).fetchone()
        if exists:
            skipped += 1
            continue
        # Note: existing schema uses parameter_value/parameter_unit (not value/unit)
        conn.execute(
            "INSERT INTO process_params "
            "(operation_type, material_grade, parameter_name, "
            "parameter_value, parameter_unit, conditions, chapter, table_ref, source_page, "
            "extraction_method, cross_validated) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (p.operation_type, p.material_grade, p.parameter_name,
             p.value, p.unit, p.conditions, p.chapter, p.table_ref,
             p.source_page, p.extraction_method, p.cross_validated)
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def write_chunks(db_path: str, chunks: list[KnowledgeChunk]) -> tuple[int, int]:
    """写入知识块到 kb_chunks。返回 (inserted, skipped)。"""
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = skipped = 0
    now = datetime.utcnow().isoformat()
    for c in chunks:
        # Idempotency: skip if same content+source_page already exists
        exists = conn.execute(
            "SELECT 1 FROM kb_chunks WHERE source_page=? AND source=? "
            "AND content=? LIMIT 1",
            (c.source_page, c.source, c.content)
        ).fetchone()
        if exists:
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO kb_chunks (content, source_page, chapter, source, created_at) "
            "VALUES (?,?,?,?,?)",
            (c.content, c.source_page, c.chapter, c.source, now)
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted, skipped
