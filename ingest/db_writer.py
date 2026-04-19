"""Database writer — writes extracted records to SQLite."""

import sqlite3
from datetime import datetime

from ingest.schemas import EquipmentSpec, KnowledgeChunk, ProcessParam, SurfaceStandard, ToleranceFit

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS cutting_params (
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
CREATE TABLE IF NOT EXISTS tolerance_fits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nominal_min REAL NOT NULL,
    nominal_max REAL NOT NULL,
    fit_code TEXT NOT NULL,
    fit_type TEXT,
    upper_deviation REAL,
    lower_deviation REAL,
    tolerance_grade TEXT,
    standard_ref TEXT,
    source_page INTEGER NOT NULL,
    chapter TEXT DEFAULT '',
    table_ref TEXT DEFAULT '',
    extraction_method TEXT NOT NULL DEFAULT 'llm_extracted',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(nominal_min, nominal_max, fit_code)
);
CREATE INDEX IF NOT EXISTS idx_tf_size ON tolerance_fits(nominal_min, nominal_max);
CREATE INDEX IF NOT EXISTS idx_tf_code ON tolerance_fits(fit_code);
CREATE INDEX IF NOT EXISTS idx_tolerance_fits_source ON tolerance_fits(source_page);
CREATE TABLE IF NOT EXISTS equipment_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_type TEXT,
    model_number TEXT,
    param_name TEXT NOT NULL,
    param_value TEXT,
    param_unit TEXT,
    source_page INTEGER NOT NULL,
    chapter TEXT,
    table_ref TEXT,
    extraction_method TEXT NOT NULL DEFAULT 'llm',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_equipment_specs_type ON equipment_specs(equipment_type);
CREATE INDEX IF NOT EXISTS idx_equipment_specs_source ON equipment_specs(source_page);
CREATE TABLE IF NOT EXISTS surface_standards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machining_method TEXT NOT NULL,
    process_condition TEXT,
    ra_min REAL,
    ra_max REAL,
    rz_min REAL,
    rz_max REAL,
    applicable_material TEXT,
    standard_ref TEXT,
    source_page INTEGER NOT NULL,
    chapter TEXT DEFAULT '',
    table_ref TEXT DEFAULT '',
    extraction_method TEXT NOT NULL DEFAULT 'llm_extracted',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(machining_method, process_condition, source_page)
);
CREATE INDEX IF NOT EXISTS idx_ss_method ON surface_standards(machining_method);
CREATE INDEX IF NOT EXISTS idx_surface_standards_source ON surface_standards(source_page);
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
    """事务性写入参数到 cutting_params。返回 (inserted, 0)。

    采用 DELETE+INSERT 事务性 upsert：按 (source, source_page) 分组，
    先删除同源同页的 LLM/VLM 提取记录，再批量插入新记录。
    """
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = 0
    try:
        conn.execute("BEGIN")
        keys = {('', p.source_page) for p in params}
        for src, pg in keys:
            conn.execute(
                "DELETE FROM cutting_params WHERE source_doc=? AND source_page=? "
                "AND extraction_method IN ('llm_extracted','vlm_fallback')",
                (src, pg))
        # Deduplicate within batch by unique key (last wins)
        seen = {}
        for p in params:
            key = (p.table_ref, p.source_page, p.operation_type, p.material_grade, p.parameter_name)
            seen[key] = p
        for p in seen.values():
            conn.execute(
                "INSERT INTO cutting_params "
                "(operation_type, material_grade, parameter_name, "
                "parameter_value, parameter_unit, conditions, chapter, table_ref, source_page, "
                "source_doc, extraction_method, cross_validated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.operation_type, p.material_grade, p.parameter_name,
                 p.value, p.unit, p.conditions, p.chapter, p.table_ref,
                 p.source_page, '', p.extraction_method, p.cross_validated)
            )
            inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return inserted, 0


def write_chunks(db_path: str, chunks: list[KnowledgeChunk]) -> tuple[int, int]:
    """事务性写入知识块到 kb_chunks。返回 (inserted, 0)。"""
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = 0
    now = datetime.utcnow().isoformat()
    try:
        conn.execute("BEGIN")
        keys = {(c.source, c.source_page) for c in chunks}
        for src, pg in keys:
            conn.execute(
                "DELETE FROM kb_chunks WHERE source=? AND source_page=?",
                (src, pg))
        for c in chunks:
            conn.execute(
                "INSERT INTO kb_chunks (content, source_page, chapter, source, created_at) "
                "VALUES (?,?,?,?,?)",
                (c.content, c.source_page, c.chapter, c.source, now)
            )
            inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return inserted, 0


def write_tolerance(db_path: str, records: list[ToleranceFit]) -> tuple[int, int]:
    """事务性写入公差配合记录到 tolerance_fits。返回 (inserted, 0)。

    采用 DELETE+INSERT 事务性 upsert：按 (source_page) 分组，
    先删除同源同页的 LLM/VLM 提取记录，再批量插入新记录。
    """
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = 0
    try:
        conn.execute("BEGIN")
        pages = {r.source_page for r in records}
        for pg in pages:
            conn.execute(
                "DELETE FROM tolerance_fits WHERE source_page=? "
                "AND extraction_method IN ('llm_extracted','vlm_fallback')",
                (pg,))
        # Deduplicate within batch by unique key (last wins)
        seen = {}
        for r in records:
            key = (r.nominal_min, r.nominal_max, r.fit_code)
            seen[key] = r
        for r in seen.values():
            conn.execute(
                "INSERT OR REPLACE INTO tolerance_fits "
                "(nominal_min, nominal_max, fit_code, fit_type, "
                "upper_deviation, lower_deviation, tolerance_grade, standard_ref, "
                "source_page, chapter, table_ref, extraction_method) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.nominal_min, r.nominal_max, r.fit_code, r.fit_type,
                 r.upper_deviation, r.lower_deviation, r.tolerance_grade, r.standard_ref,
                 r.source_page, r.chapter, r.table_ref, r.extraction_method)
            )
            inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return inserted, 0


def write_equipment(db_path: str, records: list[EquipmentSpec]) -> tuple[int, int]:
    """事务性写入设备规格记录到 equipment_specs。返回 (inserted, 0)。

    采用 DELETE+INSERT 事务性 upsert：按 (source_page) 分组，
    先删除同源同页的记录，再批量插入新记录。
    """
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = 0
    try:
        conn.execute("BEGIN")
        pages = {r.source_page for r in records}
        for pg in pages:
            conn.execute(
                "DELETE FROM equipment_specs WHERE source_page=?",
                (pg,))
        # Deduplicate within batch by unique key (last wins)
        seen = {}
        for r in records:
            key = (r.model_number, r.param_name, r.source_page)
            seen[key] = r
        for r in seen.values():
            conn.execute(
                "INSERT INTO equipment_specs "
                "(equipment_type, model_number, param_name, param_value, param_unit, "
                "source_page, chapter, table_ref, extraction_method) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (r.equipment_type, r.model_number, r.param_name, r.param_value,
                 r.param_unit, r.source_page, r.chapter, r.table_ref,
                 r.extraction_method)
            )
            inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return inserted, 0


def write_surface(db_path: str, records: list[SurfaceStandard]) -> tuple[int, int]:
    """事务性写入表面粗糙度记录到 surface_standards。返回 (inserted, 0)。

    采用 DELETE+INSERT 事务性 upsert：按 (source_page) 分组，
    先删除同源同页的 LLM/VLM 提取记录，再批量插入新记录。
    """
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    inserted = 0
    try:
        conn.execute("BEGIN")
        pages = {r.source_page for r in records}
        for pg in pages:
            conn.execute(
                "DELETE FROM surface_standards WHERE source_page=? "
                "AND extraction_method IN ('llm_extracted','vlm_fallback')",
                (pg,))
        # Deduplicate within batch by unique key (last wins)
        seen = {}
        for r in records:
            key = (r.machining_method, r.process_condition, r.source_page)
            seen[key] = r
        for r in seen.values():
            conn.execute(
                "INSERT OR REPLACE INTO surface_standards "
                "(machining_method, process_condition, ra_min, ra_max, "
                "rz_min, rz_max, applicable_material, standard_ref, "
                "source_page, chapter, table_ref, extraction_method) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.machining_method, r.process_condition, r.ra_min, r.ra_max,
                 r.rz_min, r.rz_max, r.applicable_material, r.standard_ref,
                 r.source_page, r.chapter, r.table_ref, r.extraction_method)
            )
            inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return inserted, 0
