-- Schema B: 拆专表 (按用途切分)
-- Each table targets one canonical lookup pattern. extra_json kept on each
-- for occasional table-specific extras, but typed columns should cover the
-- common case for that pattern.

PRAGMA foreign_keys = ON;

-- kb_records 不变 (跟 schema_a 完全同, 此处 inline 因为 db 是独立的)
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
CREATE INDEX IF NOT EXISTS idx_kb_branch_b ON kb_records(framework_branch);
CREATE INDEX IF NOT EXISTS idx_kb_family_b ON kb_records(family);

-- 1. 加工路线 → IT/Ra 表 (§2.3.2 PATH 系列)
CREATE TABLE IF NOT EXISTS lookup_path_precision (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    feature_kind TEXT,                  -- '外圆' / '孔' / '平面' (从 record topic 推)
    path_text TEXT NOT NULL,            -- 整条路线: '粗车→半精车→精车 (或磨)'
    it_text TEXT,
    it_min INTEGER,
    it_max INTEGER,
    ra_min REAL,
    ra_max REAL,
    applies_to_solid INTEGER,           -- 0/1 (钻/车孔区分)
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
-- 关键: method 信息通常在 record 标题, row 里只有 stage + material + ra
CREATE TABLE IF NOT EXISTS lookup_method_ra (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    method TEXT NOT NULL,         -- 从 record.subtype/topic 解析 (车端面/铣/磨/钻 等)
    stage TEXT,                   -- 粗/半精/精/精密 (row 内)
    material TEXT,
    ra_min REAL,
    ra_max REAL,
    ra_text TEXT,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 5. 表面/接合 → 推荐 Ra (§2.8.2.4 5 张静/动联接表)
CREATE TABLE IF NOT EXISTS lookup_surface_ra (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    surface_kind TEXT NOT NULL,    -- '静联接-密封-带衬垫' 等
    condition TEXT,                -- 附加约束: 'IT≤6' / 'A≤6' 等
    ra_text TEXT,                  -- 'Ra5、Ra2.5' 这种字符串
    ra_min REAL,
    ra_max REAL,
    extra_json TEXT,
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);

-- 6. 切削参数 N-维表 (§2.7) — schema_b 的关键测试
CREATE TABLE IF NOT EXISTS lookup_cutting_params (
    record_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    material TEXT,                  -- 碳素结构钢 / 铸铁及铜合金 / 不锈钢 / ...
    tool_type TEXT,                 -- 硬质合金 / 高速钢 / YG8 / YT15
    tool_shank_text TEXT,           -- '16×25' / '20×30' (字符串保原)
    operation TEXT,                 -- 粗车 / 精车 / 半精车 / 镗孔 / 切断
    workpiece_dim_text TEXT,        -- '20' / '20~40' / '≤10' (原文)
    workpiece_dim_min REAL,         -- 解析后下界 (mm)
    workpiece_dim_max REAL,         -- 解析后上界
    ap_segment_text TEXT,           -- '≤3' / '3~5' / '5~8'
    ap_min REAL,
    ap_max REAL,
    -- 输出参数 (至少一对有数据)
    f_min REAL,
    f_max REAL,
    vc_min_mps REAL,
    vc_max_mps REAL,
    n_min_rpm REAL,
    n_max_rpm REAL,
    -- 精车专用条件维度
    ra_target_um REAL,
    kappa_prime_deg TEXT,           -- '5' / '10' / '10~15' (角度也带范围)
    tool_nose_r_mm REAL,
    -- 材料附加条件
    hardness_hbw_text TEXT,         -- '143~207' / '<190' / 'null'
    heat_treat TEXT,
    extra_json TEXT,                -- regime / modifiers 等附加
    PRIMARY KEY (record_id, row_index),
    FOREIGN KEY (record_id) REFERENCES kb_records(id)
);
CREATE INDEX IF NOT EXISTS idx_cp_material ON lookup_cutting_params(material);
CREATE INDEX IF NOT EXISTS idx_cp_op ON lookup_cutting_params(operation);

-- 7. 二维网格大表 (尺寸段 × 方法 → IT + 偏差) — 11 张当前 index 占位记录的目标
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

-- 特殊数据 (螺纹精度 / 加工硬化 / 圆锥孔 / 型面) 仍留在 kb_records.payload_json,
-- 不开专表 (rows 太少不值得).
