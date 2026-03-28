# 工艺卡生成系统 (Process Card Generator)

从工程图纸 + 毛坯/设备信息，自动生成标准工艺卡 Word 文件。

## 流水线架构

```
输入:
  - 工程图纸 (PNG/JPG)
  - 毛坯信息 (文本)
  - 设备清单 (文本)
  - 材料牌号 (文本)
  - [可选] CAD 模型 JSON (精确几何数据)

流水线:
  Stage 1   图纸解析 (VLM)            → 零件特征 JSON (类型/尺寸/公差/特征)
  Stage 1.5 CAD JSON 增强 [可选]      → 合并精确几何数据到零件特征
  Stage 2   工艺框架检索 (Web + LLM)  → 典型加工路线骨架
  Stage 3   知识库检索 (PostgreSQL)    → 切削参数 + 加工经验
  Stage 4   工艺路线生成 (LLM)        → 结构化工序列表
  Stage 5   工艺卡渲染 (python-docx)  → 标准工艺卡 .docx

输出:
  - 工艺卡 Word 文件
  - Trace JSON (机器可读)
  - Trace Markdown 报告 (人可读)
```

全程带结构化追踪日志，方便团队逐环节审核和优化。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制并编辑 `config.yaml`：

| 配置项 | 说明 | 如何获取 |
|--------|------|---------|
| `llm.api_key` | DashScope API Key | 阿里云 DashScope 控制台 |
| `llm.base_url` | API 端点 | Coding Plan: `https://coding.dashscope.aliyuncs.com/v1` |
| `llm.model` | VLM 模型 (图纸解析) | 默认 `qwen3.5-plus` |
| `llm.text_model` | 文本 LLM (路线生成) | 默认 `qwen3.5-plus` |
| `database.path` | SQLite 知识库路径 | 默认 `data/knowledge.db`（自带，无需配置） |
| `web_search.enabled` | 是否启用网络搜索 | `true` / `false` |
| `web_search.llm_timeout` | LLM 调用超时(秒) | 默认 120 |

### 3. 运行

**基本用法** — 仅图纸 + 毛坯信息：

```bash
python3 main.py \
  --drawing 图纸.png \
  --blank-info "⌀103.5×L, L为零件长度" \
  --equipment "数控车床, 三轴加工中心, 车床" \
  --material "Z2CN19-10NS" \
  --output output/
```

**增强模式** — 图纸 + CAD JSON（提供精确尺寸和公差）：

```bash
python3 main.py \
  --drawing 图纸.png \
  --blank-info "⌀103.5×L, L为零件长度" \
  --equipment "数控车床, 三轴加工中心, 车床" \
  --material "Z2CN19-10NS" \
  --cad-json 模型导出.json \
  --output output/
```

### 4. 查看结果

运行后在输出目录生成：

| 文件 | 说明 |
|------|------|
| `工艺卡_YYYYMMDD_HHMMSS.docx` | 标准工艺卡 Word 文件 |
| `trace_YYYYMMDD_HHMMSS.json` | 完整 trace (机器可读) |
| `trace_YYYYMMDD_HHMMSS.md` | Trace 报告 (人可读，推荐先看这个) |

## CLI 参数

| 参数 | 必填 | 说明 | 示例 |
|------|:----:|------|------|
| `--drawing` | 是 | 工程图纸路径 (PNG/JPG) | `图纸.png` |
| `--blank-info` | 是 | 毛坯信息 | `"⌀103.5×L, L为零件长度"` |
| `--equipment` | 是 | 可用设备，逗号分隔 | `"数控车床, 三轴加工中心"` |
| `--material` | 是 | 材料牌号 | `"Z2CN19-10NS"` |
| `--cad-json` | 否 | CAD 模型 JSON 文件 | `模型.json` |
| `--output` | 否 | 输出目录 (默认 `output`) | `output/` |
| `--config` | 否 | 配置文件 (默认 `config.yaml`) | `config.yaml` |

## Trace 报告说明

Markdown trace 报告展示每个 Stage 的：
- **输入数据** — 该阶段接收到的参数
- **推理过程** — VLM/LLM 的分析逻辑和中间决策
- **搜索记录** — DuckDuckGo 搜索查询、知识库 SQL 查询及结果
- **输出结果** — 该阶段的结构化输出
- **耗时** — 各阶段耗时分布，便于定位性能瓶颈

用于团队逐环节审核和优化，每次优化可对比前后 trace 差异。

## 项目结构

```
services/process-expert/
├── main.py                          # 主入口，CLI 参数解析 + 5阶段编排
├── config.yaml                      # 配置文件（需填入 API Key 和数据库密码）
├── requirements.txt                 # Python 依赖
│
├── stages/                          # 5 个处理阶段
│   ├── stage1_drawing_analysis.py   # VLM 图纸解析 (qwen3.5-plus)
│   ├── cad_json_parser.py           # CAD JSON 精确几何解析
│   ├── stage2_web_research.py       # DuckDuckGo 搜索 + LLM 框架综合
│   ├── stage3_kb_search.py          # SQLite 本地知识库检索
│   ├── stage4_route_generation.py   # LLM 工艺路线生成
│   └── stage5_card_rendering.py     # python-docx 工艺卡渲染
│
├── tracer/                          # 追踪日志引擎
│   └── pipeline_tracer.py           # JSON + Markdown 双格式输出
│
├── templates/                       # Word 模板（预留扩展）
│
└── output/                          # 输出目录（自动创建）
    ├── test1_no_cad/                # 测试1: 仅图纸
    └── test2_with_cad/              # 测试2: 图纸 + CAD JSON
```

## 各阶段详解

### Stage 1: 图纸解析 (VLM)
- 调用 DashScope VLM API (qwen3.5-plus)，发送图纸图片
- 提取：零件类型、主要尺寸、表面粗糙度、形位公差、几何特征、技术要求
- VLM 识别的尺寸为近似值（受图片分辨率和标注清晰度影响）

### Stage 1.5: CAD JSON 增强（可选）
- 解析 Fusion 360 等 CAD 软件导出的 JSON 模型文件
- 提取精确几何数据：直径、长度、公差等级、制造信息
- 与 VLM 结果合并，补充精确尺寸和公差数据

### Stage 2: 工艺框架检索 (Web + LLM)
- DuckDuckGo 搜索材料+零件类型相关的工艺路线信息
- 搜索结果作为上下文输入 LLM，综合生成典型加工框架
- 降级策略：搜索/LLM 失败时使用预置通用框架

### Stage 3: 知识库检索 (SQLite)
- 自带本地 SQLite 知识库，无需额外数据库配置
- 三路查询：`process_params`（切削参数）+ `experience_log`（工艺经验）+ `kb_chunks` FTS5 全文检索（手册知识）
- 手册知识由 VLM 多模态管道提取（保留表格结构，非纯文本 OCR）

### Stage 4: 工艺路线生成 (LLM)
- 组装 Stage 1-3 全部结果 + 用户输入（毛坯/设备/材料）
- LLM 生成结构化工序列表（JSON 格式）
- 自动校验：工序数 >= 6、必须含领料+入库
- Token 截断策略：Stage1 2000 / Stage2 3000 / Stage3 3000 字符

### Stage 5: 工艺卡渲染 (python-docx)
- A4 横排 Word 文档
- 标准工艺卡表格：工序号、工序名、加工内容、设备、工装、检验要求
- 每道工序自动附带检验行
- 签名栏：编制/审核/批准

## 降级策略

每个阶段都有独立的错误处理和降级方案：

| 阶段 | 失败场景 | 降级行为 |
|------|---------|---------|
| Stage 1 | VLM API 不可用 | 返回 "回转体零件" 默认类型 |
| Stage 1.5 | CAD JSON 解析失败 | 跳过，仅用 VLM 结果 |
| Stage 2 | 网络搜索/LLM 超时 | 使用预置通用框架（7道工序） |
| Stage 3 | 数据库连接失败 | 返回空结果，不阻塞流程 |
| Stage 4 | LLM 输出格式异常 | 抛出异常，不生成工艺卡 |
| Stage 5 | Word 渲染失败 | 跳过，trace 仍然生成 |

## 依赖说明

| 包名 | 用途 |
|------|------|
| `openai` | 调用 DashScope API (OpenAI 兼容协议) |
| `duckduckgo-search` | 免费网络搜索（无需 API Key） |
| `python-docx` | 工艺卡 Word 文件生成 |
| `docxtpl` | Word 模板渲染（预留扩展） |
| `pyyaml` | 配置文件解析 |
| `requests` | HTTP 请求 |

## 已知限制

- VLM 尺寸提取为近似值（零件类型识别可靠，具体尺寸可能有偏差）
- 知识库数据量受源 PDF 内容限制（切削参数 + 经验记录 + 手册全文检索）
- 工时估算功能尚未实现
- DuckDuckGo 搜索在国内网络可能需要代理
- CAD JSON 目前仅支持 Fusion 360 导出格式

## 外部依赖

| 服务 | 必需 | 用途 | 获取方式 |
|------|:----:|------|---------|
| DashScope API | 是 | VLM 图纸解析 + LLM 工艺路线生成 | 阿里云 DashScope 控制台申请 |
| 互联网连接 | 否 | Stage 2 DuckDuckGo 搜索（可关闭） | 关闭: `config.yaml` 设 `web_search.enabled: false` |
| PostgreSQL | 否 | 不需要，知识库自带 SQLite | — |
