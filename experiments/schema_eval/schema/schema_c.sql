-- Schema C: EAV (Entity-Attribute-Value) 长格式
-- 每个原始 value_table row 拆成 N 个 (record_id, row_index, attr_key, value) 元组.
-- Query 形式典型:
--   SELECT v1.attr_value_text AS method, v2.attr_value_num AS ra_min
--   FROM std_attributes v1
--   JOIN std_attributes v2 USING (record_id, row_index)
--   WHERE v1.attr_key='method' AND v2.attr_key='ra_min';

PRAGMA foreign_keys = ON;

-- kb_records 不变 (跟 a/b 同 schema)
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
CREATE INDEX IF NOT EXISTS idx_kb_branch_c ON kb_records(framework_branch);
CREATE INDEX IF NOT EXISTS idx_kb_family_c ON kb_records(family);

-- 长格式属性表
CREATE TABLE IF NOT EXISTS std_attributes (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    attr_key TEXT NOT NULL,            -- 'method' / 'ra_min' / 'ap_segment' / 'operation' …
    attr_value_text TEXT,              -- string 表示 (always populated for non-null)
    attr_value_num REAL,               -- numeric 镜像 (when value is numeric)
    attr_unit TEXT,                    -- 'mm' / 'μm' / 'mm/r' / null
    PRIMARY KEY (record_id, row_index, attr_key),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_attr_key ON std_attributes(attr_key);
CREATE INDEX IF NOT EXISTS idx_attr_keyval_text ON std_attributes(attr_key, attr_value_text);

-- 便利视图: 还原成宽表 (限于 known keys), 主要用于 sanity check
CREATE VIEW IF NOT EXISTS v_widened AS
SELECT
    record_id,
    row_index,
    MAX(CASE WHEN attr_key='method' THEN attr_value_text END) AS method,
    MAX(CASE WHEN attr_key='material' THEN attr_value_text END) AS material,
    MAX(CASE WHEN attr_key='stage' THEN attr_value_text END) AS stage,
    MAX(CASE WHEN attr_key='feature' THEN attr_value_text END) AS feature,
    MAX(CASE WHEN attr_key='operation' THEN attr_value_text END) AS operation,
    MAX(CASE WHEN attr_key='workpiece_dim_text' THEN attr_value_text END) AS workpiece_dim_text,
    MAX(CASE WHEN attr_key IN ('IT','it') THEN attr_value_text END) AS it_text,
    MAX(CASE WHEN attr_key IN ('IT_min','it_min') THEN attr_value_num END) AS it_min,
    MAX(CASE WHEN attr_key IN ('IT_max','it_max') THEN attr_value_num END) AS it_max,
    MAX(CASE WHEN attr_key='ra_min' THEN attr_value_num END) AS ra_min,
    MAX(CASE WHEN attr_key='ra_max' THEN attr_value_num END) AS ra_max,
    MAX(CASE WHEN attr_key='f_min' THEN attr_value_num END) AS f_min,
    MAX(CASE WHEN attr_key='f_max' THEN attr_value_num END) AS f_max,
    MAX(CASE WHEN attr_key='vc_min_mps' THEN attr_value_num END) AS vc_min_mps,
    MAX(CASE WHEN attr_key='vc_max_mps' THEN attr_value_num END) AS vc_max_mps
FROM std_attributes
GROUP BY record_id, row_index;
