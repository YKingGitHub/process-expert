#!/usr/bin/env python3
"""
build_db.py — 从 data/seeds/ JSON 确定性构建 knowledge.db

用法:
  python data/build_db.py                     # 仅加载手工种子数据
  python data/build_db.py --include-extracted  # 额外加载 extracted/*.json
  python data/build_db.py --db path/to/db     # 指定输出路径

幂等性: 每次运行先 DROP 再 CREATE，确保结果确定性。
零外部依赖: 仅用 Python 标准库。
"""
import argparse
import glob
import json
import pathlib
import sqlite3
import sys

SCHEMA_DDL = """
DROP TABLE IF EXISTS kb_chunks_fts;
DROP TABLE IF EXISTS process_params;
DROP TABLE IF EXISTS experience_log;
DROP TABLE IF EXISTS kb_chunks;
CREATE TABLE process_params (
    id INTEGER PRIMARY KEY,
    material_grade TEXT NOT NULL,
    material_category TEXT DEFAULT '',
    operation_type TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    parameter_value TEXT NOT NULL,
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
    extraction_method TEXT DEFAULT 'manual_seed',
    cross_validated INTEGER DEFAULT 0
);
CREATE UNIQUE INDEX idx_process_params_unique
    ON process_params (table_ref, source_page, operation_type, material_grade, parameter_name);
CREATE TABLE experience_log (
    id INTEGER PRIMARY KEY,
    expert_domain TEXT NOT NULL,
    category TEXT NOT NULL,
    situation TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    outcome TEXT NOT NULL,
    outcome_type TEXT DEFAULT 'neutral',
    lesson TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    times_applied INTEGER DEFAULT 0,
    tags TEXT DEFAULT '[]',
    source TEXT DEFAULT ''
);
CREATE TABLE kb_chunks (
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
CREATE VIRTUAL TABLE kb_chunks_fts USING fts5(
    content,
    source_file,
    content='kb_chunks',
    content_rowid='id'
);
"""

PROCESS_PARAMS_COLS = [
    "material_grade", "material_category", "operation_type", "parameter_name",
    "parameter_value", "parameter_unit", "equipment", "surface_finish",
    "tolerance", "conditions", "source_doc", "confidence", "chapter",
    "table_ref", "source_page", "extraction_method", "cross_validated",
]

EXPERIENCE_LOG_COLS = [
    "expert_domain", "category", "situation", "action_taken", "outcome",
    "outcome_type", "lesson", "confidence", "times_applied", "tags", "source",
]

KB_CHUNKS_COLS = [
    "content", "source_file", "domain", "doc_type", "chapter_title",
    "page_start", "page_end", "source_page", "chapter", "source", "created_at",
]


def check_fts5(conn):
    """FTS5 可用性检查；不满足则打印错误并退出。"""
    try:
        conn.execute("CREATE VIRTUAL TABLE _fts5_test USING fts5(x)")
        conn.execute("DROP TABLE _fts5_test")
    except sqlite3.OperationalError as e:
        print(f"错误: 当前 SQLite 不支持 FTS5 ({e})", file=sys.stderr)
        print("解决方案: 升级 SQLite ≥3.35，或使用系统 Python ≥3.9 + libsqlite3-dev", file=sys.stderr)
        sys.exit(1)


def route_json(path: str):
    """根据文件名路由到对应的表名。"""
    name = pathlib.Path(path).name.lower()
    if "experience" in name:
        return "experience_log"
    if "params" in name or "param" in name:
        return "process_params"
    if "chunks" in name or "chunk" in name:
        return "kb_chunks"
    return None


def insert_records(conn, table: str, records: list):
    """向指定表批量插入记录，使用 INSERT OR IGNORE 保证幂等。"""
    if not records:
        return

    if table == "process_params":
        cols = PROCESS_PARAMS_COLS
    elif table == "experience_log":
        cols = EXPERIENCE_LOG_COLS
    elif table == "kb_chunks":
        cols = KB_CHUNKS_COLS
    else:
        print(f"警告: 未知表 {table}，跳过", file=sys.stderr)
        return

    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"

    rows = []
    for rec in records:
        row = tuple(rec.get(c) for c in cols)
        rows.append(row)

    conn.executemany(sql, rows)


def load_seed_file(conn, path: str):
    """加载单个 seed JSON 文件并插入到对应表。"""
    table = route_json(path)
    if table is None:
        print(f"警告: 无法识别文件 {path} 对应的表，跳过", file=sys.stderr)
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    insert_records(conn, table, records)


def main():
    parser = argparse.ArgumentParser(description="从 data/seeds/ 构建 knowledge.db")
    parser.add_argument(
        "--db",
        default="data/knowledge.db",
        help="输出数据库路径（默认: data/knowledge.db）",
    )
    parser.add_argument(
        "--include-extracted",
        action="store_true",
        help="额外加载 data/seeds/extracted/*.json",
    )
    args = parser.parse_args()

    db_path = pathlib.Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))

    # FTS5 可用性检查
    check_fts5(conn)

    # 重建 schema（幂等: DROP + CREATE）
    conn.executescript(SCHEMA_DDL)
    conn.commit()

    # 加载手工种子数据
    seeds_dir = pathlib.Path(__file__).parent / "seeds"
    seed_files = sorted(seeds_dir.glob("*.json"))
    for seed_file in seed_files:
        load_seed_file(conn, str(seed_file))
    conn.commit()

    # 可选: 加载 extracted/ 目录
    if args.include_extracted:
        extracted_dir = seeds_dir / "extracted"
        extracted_files = sorted(extracted_dir.glob("*.json")) if extracted_dir.exists() else []
        for ef in extracted_files:
            load_seed_file(conn, str(ef))
        conn.commit()

    # 输出行数统计
    pp_count = conn.execute("SELECT COUNT(*) FROM process_params").fetchone()[0]
    el_count = conn.execute("SELECT COUNT(*) FROM experience_log").fetchone()[0]
    kc_count = conn.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
    print(f"process_params: {pp_count} rows, experience_log: {el_count} rows, kb_chunks: {kc_count} rows")

    conn.close()


if __name__ == "__main__":
    main()
