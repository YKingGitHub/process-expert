# Process Expert — 工艺知识库 & 工艺卡生成系统

基于 LLM 的金属切削工艺知识库，支持精确参数查询 + 自动工艺卡生成。

## Quick Start（5 分钟上手）

### 1. 克隆 & 安装依赖

```bash
git clone https://github.com/YKingGitHub/process-expert.git
cd process-expert
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
export DASHSCOPE_API_KEY=<DASHSCOPE_API_KEY>
```

> 或将 `DASHSCOPE_API_KEY=<DASHSCOPE_API_KEY>` 写入项目根目录的 `.env` 文件（`python-dotenv` 已包含在依赖中）。

### 3. 构建知识库

```bash
python data/build_db.py
# 输出: process_params: 63 rows, experience_log: 23 rows, kb_chunks: 0 rows
```

无需 API Key，零配置，纯本地构建。

### 4. 查询参数

```bash
python query.py --material 45钢
python query.py --material 45钢 --operation 车削
python query.py --help
```

### 5. 生成工艺卡（需图纸）

```bash
python main.py \
  --drawing 图纸.png \
  --blank-info "⌀50×100, L为零件长度" \
  --equipment "数控车床, 三轴加工中心, 车床" \
  --material "45钢" \
  --output output/
```

---

## 环境变量

| 变量名 | 必需 | 说明 | 示例 |
|--------|:----:|------|------|
| `DASHSCOPE_API_KEY` | 是（LLM功能） | 阿里云 DashScope API Key，用于图纸解析、工艺路线生成、工艺卡生成 | `<DASHSCOPE_API_KEY>` |

> `data/build_db.py` 和 `query.py --material` 基础查询**不需要** API Key，可离线运行。
> 仅 `main.py`（工艺卡生成）和 `query.py` LLM 增强模式需要 `DASHSCOPE_API_KEY`。

---

## 知识库管理

### 构建知识库

```bash
# 仅加载手工种子数据（63条参数 + 23条经验，无需API Key）
python data/build_db.py

# 指定输出路径
python data/build_db.py --db path/to/my.db

# 额外加载本地提取结果（需先在本地运行 ingest 管线）
python data/build_db.py --include-extracted
```

每次运行都是确定性重建（DROP + CREATE + INSERT），幂等无副作用。

### 添加手工数据（贡献指南）

手工种子数据存放在 `data/seeds/` 目录，使用 JSON 格式，可 code review、可 git blame。

**添加工艺参数**：编辑 `data/seeds/manual_params.json`，在 `records` 数组末尾追加：

```json
{
  "material_grade": "45钢",
  "material_category": "碳钢",
  "operation_type": "车削（粗加工）",
  "parameter_name": "推荐切削速度",
  "parameter_value": "120-180",
  "parameter_unit": "m/min",
  "equipment": "",
  "surface_finish": "",
  "tolerance": "",
  "conditions": "",
  "source_doc": "来源文献",
  "confidence": 0.9,
  "chapter": "",
  "table_ref": "",
  "source_page": 0,
  "extraction_method": "manual_seed",
  "cross_validated": 0
}
```

**添加工艺经验**：编辑 `data/seeds/manual_experience.json`，在 `records` 数组末尾追加：

```json
{
  "expert_domain": "金属切削",
  "category": "刀具管理",
  "situation": "高速切削时刀具出现积屑瘤",
  "action_taken": "降低切削速度至60m/min以下，使用切削液",
  "outcome": "积屑瘤消除，表面粗糙度改善",
  "outcome_type": "positive",
  "lesson": "积屑瘤形成区间约80-120m/min，避开该区间",
  "confidence": 0.85,
  "times_applied": 0,
  "tags": "[]",
  "source": ""
}
```

添加后重新运行 `python data/build_db.py` 使变更生效。提交时只需提交 JSON 文件，`knowledge.db` 由 `.gitignore` 排除。

### 运行入库管线（LLM 提取）

```bash
# 将 PDF 参考资料提取入库（需要 DASHSCOPE_API_KEY）
python ingest/cli.py --pdf references/工艺知识库.pdf --output data/seeds/extracted/

# 入库后重建 DB（包含提取结果）
python data/build_db.py --include-extracted
```

提取结果保存在 `data/seeds/extracted/`（本地保留，不纳入 git），团队协作时各自本地重跑。

---

## 项目结构

```
process-expert/
├── main.py                          # 主入口：CLI 参数解析 + 5阶段编排
├── query.py                         # 知识库查询 CLI
├── config.yaml                      # 配置文件（API 端点、模型、数据库路径）
├── requirements.txt                 # Python 依赖
│
├── data/
│   ├── build_db.py                  # 知识库构建脚本（确定性重建）
│   └── seeds/
│       ├── manual_params.json       # 手工工艺参数种子（63条，git 跟踪）
│       ├── manual_experience.json   # 手工工艺经验种子（23条，git 跟踪）
│       └── extracted/               # LLM 提取结果（本地保留，.gitignore）
│
├── stages/                          # 5个处理阶段
│   ├── stage1_drawing_analysis.py   # Stage 1: VLM 图纸解析
│   ├── cad_json_parser.py           # Stage 1.5: CAD JSON 增强
│   ├── stage2_web_research.py       # Stage 2: 网络搜索 + LLM 框架
│   ├── stage3_kb_search.py          # Stage 3: 知识库检索
│   ├── stage4_route_generation.py   # Stage 4: 工艺路线生成
│   └── stage5_card_rendering.py     # Stage 5: 工艺卡渲染
│
├── ingest/                          # 入库管线（PDF → 知识库）
│   └── cli.py                       # 入库 CLI
│
├── experiments/                     # 知识库正确性、Agent 查询、计算能力 POC
│   ├── README.md                    # 实验阅读入口和推荐顺序
│   ├── agent_query_eval/            # Agent 查询 family/contract/citation 评测
│   ├── vlm_source_pdf_process_cards/ # 源 PDF 工艺卡 VLM 抽取与 gold 对比
│   ├── calculation_ready_extraction/# 质量门禁、路线合并、确定性余量计算
│   └── prose_principle_extraction/  # 正文原则类知识抽取
│
├── process_calc/                    # Sprint C 确定性计算层 (frozen public contract)
│   ├── __init__.py                  # exports calculate, METHOD_REGISTRY, errors
│   ├── dispatcher.py                # calculate(method_id, **params) entry
│   ├── method_registry.py           # method_id → callable
│   ├── result.py                    # CalculationResult + build_result helper
│   ├── tolerance_lookup.py          # ISO 286-1 H6/H7/H8 + h6/h7/h8 + g6
│   ├── dimension_chain.py           # closed_loop_basic_size + extreme_tolerance + reverse
│   ├── machining_allowance.py       # finish_to_grind_allowance (textbook p.108)
│   ├── design.md                    # Sprint C Phase 1 design
│   └── README.md                    # public contract + how to add methods
│
├── tracer/                          # 追踪日志引擎
│   └── pipeline_tracer.py           # JSON + Markdown 双格式输出
│
├── templates/                       # Word 模板（预留扩展）
└── references/                      # 参考 PDF（本地保留，.gitignore）
```

### 实验目录怎么读

`experiments/` 是本周知识库正确性工作的主要可复现产物。它不直接改生产 Stage 1-5 流程，而是把关键假设拆成可读报告、固定 fixture 和 pytest：

- `experiments/README.md`：总入口，说明阅读顺序、目录结构、样例发现和测试命令
- `experiments/vlm_source_pdf_process_cards/report.md`：说明为什么旧 POC 提取不能直接作为计算真值
- `experiments/calculation_ready_extraction/report.md`：说明如何从源 PDF VLM 输出进入质量门禁和确定性计算
- `experiments/agent_query_eval/report.md`：说明 Agent 查询知识时需要满足的 family、contract、citation 要求

完整回归命令：

```bash
python3 -m pytest experiments/ tests/ -q
```

按目录查看测试规模：

| 测试目录 | 测试数 | Sprint |
|------|------:|---|
| `experiments/agent_query_eval/` | 10 | A |
| `experiments/calculation_ready_extraction/` | 5 | A |
| `experiments/process_calc_extracted_content/` | 10 | A |
| `experiments/prose_principle_extraction/` | 4 | A |
| `experiments/vlm_source_pdf_process_cards/` | 3 | A |
| `tests/test_process_calc/` | 33 | C |

---

## CLI 参考

### query.py — 参数查询

```bash
python query.py --help
python query.py --material 45钢
python query.py --material 45钢 --operation 车削
python query.py --material 45钢 --operation 铣削
```

| 参数 | 说明 |
|------|------|
| `--material` | 材料牌号（模糊匹配） |
| `--operation` | 工序类型（可选，进一步过滤） |

### ingest/cli.py — 知识库入库

```bash
python ingest/cli.py --pdf references/工艺知识库.pdf
python ingest/cli.py --help
```

需要 `DASHSCOPE_API_KEY`。

### main.py — 工艺卡生成

```bash
python main.py \
  --drawing 图纸.png \
  --blank-info "⌀50×100, L为零件长度" \
  --equipment "数控车床, 三轴加工中心, 车床" \
  --material "45钢" \
  [--cad-json 模型.json] \
  [--output output/] \
  [--config config.yaml]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--drawing` | 是 | 工程图纸路径 (PNG/JPG) |
| `--blank-info` | 是 | 毛坯信息 |
| `--equipment` | 是 | 可用设备，逗号分隔 |
| `--material` | 是 | 材料牌号 |
| `--cad-json` | 否 | CAD 模型 JSON（Fusion 360 导出） |
| `--output` | 否 | 输出目录（默认 `output/`） |
| `--config` | 否 | 配置文件（默认 `config.yaml`） |

---

## 流水线架构

```
输入: 工程图纸 + 毛坯/设备/材料信息

Stage 1   图纸解析 (VLM)            → 零件特征 JSON
Stage 1.5 CAD JSON 增强 [可选]      → 合并精确几何数据
Stage 2   工艺框架检索 (Web + LLM)  → 典型加工路线骨架
Stage 3   知识库检索 (SQLite)       → 切削参数 + 加工经验 + 手册全文
Stage 4   工艺路线生成 (LLM)        → 结构化工序列表
Stage 5   工艺卡渲染 (python-docx)  → 标准工艺卡 .docx

输出: 工艺卡 Word 文件 + Trace JSON + Trace Markdown 报告
```

---

## 贡献指南

### 添加手工参数种子

1. 编辑 `data/seeds/manual_params.json` 或 `data/seeds/manual_experience.json`
2. 在 `records` 数组末尾追加新记录（参考上方字段说明）
3. 运行 `python data/build_db.py` 验证构建成功
4. 提交 JSON 文件：`git add data/seeds/ && git commit -m "feat(seeds): 添加XX材料XX工序参数"`

### 提交入库结果

LLM 提取结果（`data/seeds/extracted/`）不纳入 git，团队各自本地保留。如需共享提取结果，将对应 JSON 文件整理后移入 `data/seeds/` 并提交。

### 代码贡献

- 各 Stage 逻辑独立，新增功能优先在对应 `stages/stage*.py` 中扩展
- 保持每个 Stage 的降级策略：失败时返回空结果，不阻塞后续阶段

---

## 依赖说明

| 包名 | 用途 |
|------|------|
| `openai` | 调用 DashScope API（OpenAI 兼容协议） |
| `duckduckgo-search` | 网络搜索（无需 API Key） |
| `python-docx` | 工艺卡 Word 文件生成 |
| `pyyaml` | 配置文件解析 |
| `python-dotenv` | 读取 `.env` 环境变量 |

---

## 已知限制

- VLM 尺寸提取为近似值（零件类型识别可靠，具体尺寸可能有偏差）
- clone 后知识库仅含 63 条手工参数 + 23 条经验；完整数据需本地重跑 `ingest/cli.py`
- DuckDuckGo 搜索在部分网络环境可能需要代理
- CAD JSON 目前仅支持 Fusion 360 导出格式
- 工时估算功能尚未实现
