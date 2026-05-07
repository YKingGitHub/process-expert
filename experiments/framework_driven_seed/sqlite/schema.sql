-- Framework-driven seed SQLite schema (Phase 3 ingest)
--
-- Two-layer:
--   1. kb_records  — every seed record, header fields + payload JSON blob
--   2. std_value_rows — flattened rows from STD records' value_table[],
--      with typed columns where common. extra_json captures
--      table-specific fields not modelled here.
--
-- Design choices:
--   - Single value_rows table (not one-per-textbook-table) because the
--     fundamental query patterns are "method × workpiece_dim → it/ra/dev"
--     and "method × stage × material → ra"; one wide table with NULLs
--     keeps process_calc lookup methods simple.
--   - extra_json keeps tables like 表 4-30 (机床平均经济精度) representable
--     without schema explosion for niche columns (圆度/圆柱度/平面度 etc.).
--   - Foreign keys + indices on the lookup-driving columns (method,
--     framework_branch, dim ranges).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS kb_records (
    id TEXT PRIMARY KEY,
    family TEXT NOT NULL CHECK(family IN ('经验','标准','计算','案例')),
    prefix TEXT NOT NULL CHECK(prefix IN ('EXP','STD','CALC','CASE')),
    framework_branch TEXT NOT NULL,
    subtype TEXT,
    topic TEXT NOT NULL,
    source_doc TEXT NOT NULL,
    source_page INTEGER NOT NULL,
    source_ref TEXT,
    source_text TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    quality_flags_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kb_branch ON kb_records(framework_branch);
CREATE INDEX IF NOT EXISTS idx_kb_family ON kb_records(family);
CREATE INDEX IF NOT EXISTS idx_kb_subtype ON kb_records(subtype);

CREATE TABLE IF NOT EXISTS std_value_rows (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    -- Method / process descriptor
    method TEXT,
    method_group TEXT,
    feature TEXT,
    stage TEXT,           -- 粗 / 半精 / 精 / 精密
    material TEXT,
    -- Workpiece dimension axis
    workpiece_dim_text TEXT,
    workpiece_dim_min REAL,
    workpiece_dim_max REAL,
    workpiece_dim_unit TEXT,
    -- Achievable precision
    it TEXT,
    it_min INTEGER,
    it_max INTEGER,
    -- Numeric values
    ra_min REAL,
    ra_max REAL,
    deviation_text TEXT,
    deviation_um REAL,
    error_text TEXT,
    error_mm_min REAL,
    error_mm_max REAL,
    -- Catch-all for table-specific extras (e.g. 4-30 圆度/圆柱度)
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_val_method ON std_value_rows(method);
CREATE INDEX IF NOT EXISTS idx_val_method_group ON std_value_rows(method_group);
CREATE INDEX IF NOT EXISTS idx_val_feature ON std_value_rows(feature);
CREATE INDEX IF NOT EXISTS idx_val_stage ON std_value_rows(stage);
CREATE INDEX IF NOT EXISTS idx_val_dims ON std_value_rows(workpiece_dim_min, workpiece_dim_max);

-- Convenience view: STD records with their value_table flattened
CREATE VIEW IF NOT EXISTS v_std_lookup AS
SELECT
    r.id AS record_id,
    r.framework_branch,
    r.topic,
    r.subtype,
    r.source_page,
    v.row_index,
    v.method,
    v.method_group,
    v.feature,
    v.stage,
    v.material,
    v.workpiece_dim_text,
    v.workpiece_dim_min,
    v.workpiece_dim_max,
    v.it,
    v.it_min,
    v.it_max,
    v.ra_min,
    v.ra_max,
    v.deviation_text,
    v.deviation_um,
    v.error_text,
    v.error_mm_min,
    v.error_mm_max,
    v.extra_json
FROM kb_records r
LEFT JOIN std_value_rows v ON v.record_id = r.id
WHERE r.family = '标准';
