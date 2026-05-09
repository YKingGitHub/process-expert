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

-- 7a. 加工余量 (尺寸段 × 长度段 × 操作 → mm 余量) — Ch6 §2.9.1
CREATE TABLE IF NOT EXISTS lookup_machining_allowance (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    feature_kind TEXT,                 -- '外圆'/'孔'/'端面'/'切断'
    operation TEXT,                    -- 粗车/半精车/精车/磨/钻/扩/铰/切断/...
    material TEXT,                     -- 钢/圆钢/方钢/钢板/铸铁/...
    size_segment_text TEXT,
    size_min REAL,
    size_max REAL,
    length_segment_text TEXT,
    length_min REAL,
    length_max REAL,
    heat_treat TEXT,
    allowance_text TEXT,
    allowance_mm_min REAL,
    allowance_mm_max REAL,
    extra_json TEXT,                   -- 工序尺寸链 (e.g. drill_1st_mm) 等附加
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_alw_feature ON lookup_machining_allowance(feature_kind);
CREATE INDEX IF NOT EXISTS idx_alw_operation ON lookup_machining_allowance(operation);

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
-- Principle family (new in 2026-05-09-03 Ch4 redesign)
-- 替代经验型 record 仅压在 payload_json blob 里、SQL 不可查的旧状态.
-- 仍保留 kb_records 头作为 source-of-truth, 但平表化的内容专为查询.
-- =========================================================================

-- 因素 / 影响 / 改善措施 三段式 (Ch4 表 4-1, 4-2, 4-3, 4-32, 4-33, 4-42, 4-43)
CREATE TABLE IF NOT EXISTS principle_factor_remedy (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    topic_kind TEXT NOT NULL,        -- 'dimension_error' / 'form_error' / 'position_error'
                                     -- / 'roughness_cutting' / 'roughness_grinding'
                                     -- / 'hardening' / 'residual_stress'
    factor_group TEXT,               -- 一级因素 (e.g. "工艺系统热变形")
    factor_text TEXT NOT NULL,       -- 二级因素 (e.g. "机床热变形")
    impact_text TEXT NOT NULL,       -- 对加工质量的影响
    remedy_text TEXT NOT NULL,       -- 改善措施
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_pfr_topic ON principle_factor_remedy(topic_kind);
CREATE INDEX IF NOT EXISTS idx_pfr_factor ON principle_factor_remedy(factor_text);

-- 振动专表 (Ch4 表 4-44 强迫振动, 4-45 自激振动) — 4 列 wide-cell
CREATE TABLE IF NOT EXISTS principle_vibration (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    vibration_kind TEXT NOT NULL,    -- 'forced' / 'self_excited'
    feature_text TEXT NOT NULL,      -- "特点" 列
    cause_text TEXT NOT NULL,        -- "产生原因"
    remedy_text TEXT NOT NULL,       -- "消减措施"
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- =========================================================================
-- New lookup tables (3) — 表 shape 与现有 8 张不对位, 单独建表 (一书表 → 一 DB 表 极端原则)
-- =========================================================================

-- 8. 钻孔路径(IT × 孔径 × 实/铸 → 路径列表) — Ch4 表 4-6, 4-7
CREATE TABLE IF NOT EXISTS lookup_drilling_path_by_tier (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    machine_kind TEXT NOT NULL,            -- '钻床+钻模' / '车床(自动/转塔)'
    it_tier_text TEXT NOT NULL,            -- '12~13' / '11' / '10~9' / '8~7' / '6~5'
    it_min INTEGER, it_max INTEGER,
    blank_kind TEXT NOT NULL,              -- 'solid' / 'preformed'
    bore_segment_text TEXT,
    bore_min REAL, bore_max REAL,
    path_steps_json TEXT NOT NULL,         -- ["钻孔","扩孔","铰孔"]
    path_steps_text TEXT NOT NULL,         -- 同上的人读形式
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_dpt_machine ON lookup_drilling_path_by_tier(machine_kind);
CREATE INDEX IF NOT EXISTS idx_dpt_blank ON lookup_drilling_path_by_tier(blank_kind);

-- 9. 机床形位精度(机床类型 × 加工尺寸段 → 多维形位经济精度) — Ch4 表 4-30
CREATE TABLE IF NOT EXISTS lookup_machine_geometry (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    machine_type TEXT NOT NULL,            -- '卧式车床' / '外圆磨床' / '卧式镗床' / ...
    machine_subtype TEXT,                  -- e.g. '高精度' / '无心磨床'
    capacity_text TEXT,                    -- "最大加工直径 ≤400" / "镗杆直径 ≤100"
    capacity_min REAL, capacity_max REAL,
    metric_kind TEXT NOT NULL,             -- '圆度' / '圆柱度' / '平面度' / '平行度' / '垂直度'
    metric_text TEXT NOT NULL,             -- 原值文本 (含分母, e.g. "0.0075/100")
    metric_value REAL,                     -- 数值部分 (mm)
    metric_per_text TEXT,                  -- 分母 ("100" / "300" / "全长")
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_mg_type ON lookup_machine_geometry(machine_type);
CREATE INDEX IF NOT EXISTS idx_mg_metric ON lookup_machine_geometry(metric_kind);

-- 10. 加工方法 → 硬化程度/硬化层深度 — Ch4 表 4-41
CREATE TABLE IF NOT EXISTS lookup_hardening_depth (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    method TEXT NOT NULL,                  -- '普通车和高速车' / '精密车' / '钻和扩' / ...
    n_pct_avg_min REAL,                    -- 冷硬程度 N% 平均 (range)
    n_pct_avg_max REAL,
    n_pct_max REAL,                        -- 最大值
    hc_avg_min_um REAL,                    -- 硬化层 hc μm 平均 (range)
    hc_avg_max_um REAL,
    hc_max_um REAL,                        -- 硬化层最大值
    note TEXT,                             -- 注脚
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_hd_method ON lookup_hardening_depth(method);

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
