"""Database writer — writes extracted records to SQLite."""

import sqlite3
from datetime import datetime

from ingest.schemas import KnowledgeChunk, ProcessParam


def write_params(db_path: str, params: list[ProcessParam]) -> tuple[int, int]:
    """写入参数到 process_params。返回 (inserted, skipped)。"""
    conn = sqlite3.connect(db_path)
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
