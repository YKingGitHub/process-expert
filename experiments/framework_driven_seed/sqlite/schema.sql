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

-- =========================================================================
-- Schema v2 — 7 specialized lookup tables (winner of 2026-05-09-01 schema A/B/C
-- experiment). std_value_rows above kept for backward-compat with raw_sql in
-- pipeline-eval traces. process_calc/lookup_kb.py queries the specialized
-- tables below for 0-friction lookups.
-- =========================================================================

-- 1. 加工路线 → IT/Ra (§2.3.2 PATH 系列)
CREATE TABLE IF NOT EXISTS lookup_path_precision (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    feature_kind TEXT,
    path_text TEXT NOT NULL,
    it_text TEXT,
    it_min INTEGER,
    it_max INTEGER,
    ra_min REAL,
    ra_max REAL,
    applies_to_solid INTEGER,
    applies_to_preformed INTEGER,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 2. 单一方法 → 经济精度 IT (§2.8.1.4-* 单方法表 + METHOD-IT-CHART)
CREATE TABLE IF NOT EXISTS lookup_method_economic_it (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    method TEXT NOT NULL,
    feature TEXT,
    it_text TEXT,
    it_min INTEGER,
    it_max INTEGER,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 3. 方法 → 定位/位置误差 (mm) — METHOD-ERRORS / PARALLEL-HOLE-POS / PERP-HOLE-POS
CREATE TABLE IF NOT EXISTS lookup_method_position_error (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    method TEXT NOT NULL,
    feature TEXT,
    error_text TEXT,
    error_mm_min REAL,
    error_mm_max REAL,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 4. 方法 → 可达 Ra (§2.8.2.1 RA-* 12 张表)
CREATE TABLE IF NOT EXISTS lookup_method_ra (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    method TEXT NOT NULL,
    stage TEXT,
    material TEXT,
    ra_min REAL,
    ra_max REAL,
    ra_text TEXT,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 5. 表面/接合 → 推荐 Ra (§2.8.2.4)
CREATE TABLE IF NOT EXISTS lookup_surface_ra (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    surface_kind TEXT NOT NULL,
    condition TEXT,
    ra_text TEXT,
    ra_min REAL,
    ra_max REAL,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 6. 切削参数 N-维表 (§2.7)
CREATE TABLE IF NOT EXISTS lookup_cutting_params (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    material TEXT,
    tool_type TEXT,
    tool_shank_text TEXT,
    operation TEXT,
    workpiece_dim_text TEXT,
    workpiece_dim_min REAL,
    workpiece_dim_max REAL,
    ap_segment_text TEXT,
    ap_min REAL,
    ap_max REAL,
    f_min REAL,
    f_max REAL,
    vc_min_mps REAL,
    vc_max_mps REAL,
    n_min_rpm REAL,
    n_max_rpm REAL,
    ra_target_um REAL,
    kappa_prime_deg TEXT,
    tool_nose_r_mm REAL,
    hardness_hbw_text TEXT,
    heat_treat TEXT,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_cp_material ON lookup_cutting_params(material);
CREATE INDEX IF NOT EXISTS idx_cp_op ON lookup_cutting_params(operation);

-- 7. 二维网格大表 (尺寸段 × 方法 → IT + 偏差) — 11 张 index 占位的目标
CREATE TABLE IF NOT EXISTS lookup_size_method_grid (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    size_segment_text TEXT,
    size_min REAL,
    size_max REAL,
    method TEXT NOT NULL,
    it_text TEXT,
    it_min INTEGER,
    it_max INTEGER,
    deviation_um_text TEXT,
    deviation_um_min REAL,
    deviation_um_max REAL,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- =========================================================================
-- Convenience view: STD records with std_value_rows flattened (legacy, kept
-- for backward-compat with pipeline-eval raw_sql)
-- =========================================================================
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
