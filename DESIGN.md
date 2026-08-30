# 工艺卡生成系统 — 设计文档

## 1. 系统目标

将传统的工艺编制流程（工程师手动分析图纸 → 查阅手册 → 编写工艺卡）自动化为：

```
工程图纸 → AI 分析 → 知识检索 → 工艺路线生成 → 标准工艺卡 Word
```

核心价值：**将数小时的工艺编制缩短到分钟级**，同时保留完整的推理过程供工程师审核。

## 2. 整体架构

```
                    ┌─────────────┐
                    │   main.py   │  CLI 入口 + 流程编排
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ┌────▼─────┐   ┌─────▼──────┐   ┌─────▼──────┐
     │ config   │   │  tracer/   │   │  stages/   │
     │ .yaml    │   │ pipeline   │   │ 5+1 阶段   │
     │          │   │ _tracer.py │   │            │
     └──────────┘   └────────────┘   └────────────┘
                                           │
                    ┌──────────────────────┼──────────────────┐
                    │           │          │         │        │
              ┌─────▼───┐ ┌────▼───┐ ┌────▼──┐ ┌───▼──┐ ┌──▼───┐
              │ Stage 1  │ │Stage 2 │ │Stage 3│ │Stg 4 │ │Stg 5 │
              │ VLM 解析 │ │Web+LLM │ │KB 检索│ │路线生│ │Word  │
              │          │ │        │ │       │ │成    │ │渲染  │
              └────┬─────┘ └───┬────┘ └───┬───┘ └──┬───┘ └──┬───┘
                   │           │          │        │        │
              DashScope    DuckDuckGo  PostgreSQL  DashScope  python
              VLM API      + DashScope  直连       Text API  -docx
                           Text API
```

## 3. 数据流设计

### 3.1 阶段间数据传递

每个阶段的输出作为下一阶段的输入，通过 Python dict 传递：

```
Stage 1 输出 (part_features: dict)
  ├── part_type: str           "盘类"
  ├── main_dimensions: dict    {"overall": "φ50 x 20 mm", "key_dimensions": [...]}
  ├── surface_finish: list     [{"surface": "...", "Ra": "Ra3.2", "method": "..."}]
  ├── geometric_tolerances: list
  ├── features: list           [{"name": "中心孔", "specification": "φ20(+0.10/0)"}]
  ├── technical_requirements: list
  ├── material: str
  │
  │ [如果提供 --cad-json]
  ├── cad_dimensions: dict     精确尺寸（从 CAD JSON 解析，单位 mm）
  ├── cad_features: list       精确几何特征
  ├── cad_tolerances: list     精确公差信息
  └── cad_sequence: list       CAD 建模顺序（辅助理解零件结构）

Stage 2 输出 (framework: dict)
  ├── typical_sequence: list   [{"op_name": "粗车", "key_points": [...], "equipment_type": "车床"}]
  ├── quality_notes: list      ["不锈钢加工注意排屑", ...]
  └── _web_snippets: list      [原始搜索结果摘要，传递给 Stage 4]

Stage 3 输出 (kb_results: dict)
  ├── params: dict             {"车削": [...参数行...]}  按工序类型分组
  └── experiences: list        [{"situation": "...", "action": "...", "lesson": "..."}]

Stage 4 输出 (process_route: list[dict])
  └── [
        {
          "seq": "05",           工序编号
          "op_name": "领料",     工序名称
          "op_type": "领料",     工序类型
          "content": ["..."],    加工内容（多条）
          "equipment": "无",     设备
          "tooling": "...",      工装/量具
          "inspection": "..."    检验要求
        },
        ...
      ]

Stage 5 输出
  └── 工艺卡_YYYYMMDD_HHMMSS.docx   A4 横排 Word 文件
```

### 3.2 Token 预算控制

Stage 4 组装所有上下文送入 LLM，通过字符截断控制 token 消耗：

| 输入源 | 字符上限 | 优先级 | 截断策略 |
|--------|:-------:|:------:|---------|
| Stage 1 (零件特征) | 2,000 | 高 | 直接截断 |
| Stage 2 (工艺框架) | 3,000 | 中 | 直接截断 |
| Stage 3 (知识库) | 3,000 | 分层 | params > experience > web，高优先级吃低优先级余量 |

总 prompt 约 3,000-5,000 tokens，max_tokens=8192 留足输出空间。

## 4. 各模块设计

### 4.1 Stage 1 — VLM 图纸解析

**输入**: 工程图纸图片 (PNG/JPG)
**调用**: DashScope qwen3.5-plus VLM API
**方法**: 图片 base64 编码 → 多模态消息 → JSON 解析

关键设计决策：
- **JSON 解析三级降级**: 直接解析 → 正则提取 `{...}` → 逐字段正则
- **VLM 不是精确工具**: 零件类型（盘类/轴类）识别可靠，但具体尺寸值可能有偏差
- **补偿方案**: CAD JSON 提供精确尺寸，两者合并后 Stage 4 可得到更准确的上下文

### 4.2 CAD JSON 解析器

**输入**: CAD 软件导出的 JSON (目前支持 Fusion 360 格式)
**输出**: 精确几何特征（直径、长度、公差、建模顺序）

解析逻辑：
- Sketch → profiles → Circle3D/Arc3D/Line3D → 直径/长度
- ExtrudeFeature → 拉伸距离 → 零件高度/深度
- FilletFeature → 圆角半径
- manufacturing_info → 公差等级和数值
- 所有数值从米(m)转换为毫米(mm)

### 4.3 Stage 2 — 网络搜索 + LLM 框架综合

**输入**: 零件类型 + 材料牌号
**调用**: DuckDuckGo API + DashScope LLM

流程：
1. 构建 2-3 个搜索查询（材料+零件类型+工艺关键词）
2. DuckDuckGo 搜索，每个查询取 Top 5 结果
3. 去重后的搜索摘要作为 LLM 上下文
4. LLM 综合搜索结果 + 自身知识，输出典型加工框架

降级策略：
- DuckDuckGo 不可用 → 仅用 LLM 自身知识
- LLM 超时/失败 → 返回预置通用框架 (GENERIC_ROTATIONAL_FRAMEWORK)

### 4.4 Stage 3 — 知识库检索

**输入**: 材料牌号 + 工序类型列表
**调用**: 本地 SQLite (`data/knowledge.db`)

三路查询：
1. `process_params` 表 — `material_grade LIKE '%材料%'` 切削参数
2. `experience_log` 表 — `domain = 'process' ORDER BY confidence DESC LIMIT 20` 工艺经验
3. `kb_chunks` FTS5 全文检索 — 手册知识（金属切削工艺技术手册等）

设计决策：
- **自带 SQLite 而非 PostgreSQL**: 打包发布无需外部数据库，同事拿到即可运行
- **知识来源**: 由 VLM 多模态管道（V2）从 PDF 提取，保留表格和结构
- **按工序类型分组参数**: 方便 Stage 4 按工序匹配切削参数

### 4.5 Stage 4 — 工艺路线生成

**输入**: Stage 1-3 全部结果 + 用户参数
**调用**: DashScope qwen3.5-plus LLM

这是核心阶段，组装完整上下文后调用 LLM 生成结构化工艺路线。

校验规则：
- 工序数量 >= 6
- 必须包含"领料"和"入库"
- 工序编号从 "05" 开始，步长 5
- 每道工序必须有：seq, op_name, op_type, content, equipment, tooling, inspection

### 4.6 Stage 5 — 工艺卡渲染

**输入**: 工艺路线 (list[dict]) + 零件信息
**输出**: A4 横排 Word 文件

表格结构：
```
┌──────┬──────┬──────────────────┬──────────┬──────────┬──────────────┐
│工序号│工序名│    加工内容       │   设备   │ 工装/量具│  检验要求    │
├──────┼──────┼──────────────────┼──────────┼──────────┼──────────────┤
│  05  │ 领料 │ 1. 核对材料...   │   无     │ 卷尺     │ 材料核对     │
│      │      │ 2. 检查毛坯...   │          │          │              │
├──────┼──────┼──────────────────┼──────────┼──────────┼──────────────┤
│      │      │ ☑ 检验要求描述   │          │          │              │  ← 检验行
├──────┼──────┼──────────────────┼──────────┼──────────┼──────────────┤
│  10  │ 粗车 │ ...              │ 数控车床 │ ...      │ ...          │
└──────┴──────┴──────────────────┴──────────┴──────────┴──────────────┘

签名栏: 编制 ____  审核 ____  批准 ____  日期 ____
```

## 5. 追踪日志 (Tracer) 设计

PipelineTracer 贯穿整个流水线，记录每个阶段的完整执行过程。

### 5.1 API

```python
tracer = PipelineTracer()
tracer.start(run_id, input_summary)      # 开始流水线

tracer.begin_stage(name, input_data)     # 开始某阶段
tracer.log_reasoning(text)               # 记录推理过程
tracer.log_search_result(source, query, results_summary)  # 记录搜索
tracer.log_error(error)                  # 记录错误
tracer.end_stage(output_data)            # 结束阶段

json_path, md_path = tracer.finish(output_dir)  # 输出文件
```

### 5.2 输出格式

**JSON** (机器可读): 完整的嵌套结构，包含每个阶段的所有事件和时间戳。
**Markdown** (人可读): 按阶段分节，展示输入/推理/搜索/输出/耗时。

## 6. 配置设计

`config.yaml` 集中管理所有外部依赖配置：

```yaml
llm:
  base_url: "..."        # DashScope API 端点
  api_key: "..."         # API Key（不要提交到 Git）
  model: "qwen3.5-plus"  # VLM 模型
  text_model: "qwen3.5-plus"  # 文本 LLM
  max_tokens: 8192
  temperature: 0.3

database:
  path: "data/knowledge.db"  # 自带 SQLite，无需配置

web_search:
  enabled: true          # 是否启用网络搜索
  timeout: 15            # DuckDuckGo 超时(秒)
  llm_timeout: 120       # LLM 综合超时(秒)
```

**安全提醒**: `api_key` 不要提交到代码仓库，使用时从环境变量或私有配置复制。

## 7. 扩展点

| 方向 | 当前状态 | 扩展方案 |
|------|---------|---------|
| 更多图纸格式 | PNG/JPG | 支持 DXF/PDF 解析 |
| 更多 CAD 格式 | Fusion 360 JSON | 支持 STEP/IGES 解析 |
| 工时估算 | 未实现 | Stage 4.5: 基于工序+参数估算工时 |
| 模板系统 | python-docx 硬编码 | templates/ 目录 + docxtpl 模板渲染 |
| 知识库扩充 | 切削参数 + 经验 + 手册 FTS | 持续入库 + 用户反馈闭环 |
| 批量处理 | 单图纸 | 支持目录批量输入 |
| Web UI | CLI | FastAPI + 前端界面 |
