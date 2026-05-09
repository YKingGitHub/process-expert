# CLAUDE.md — process-expert

工艺专家知识库 + 端到端规程生成 pipeline 项目。

## 全景指针

- **设计文档**: 在 ai-assistant 仓库 `Projects/process-expert/designs/` (本仓库不存 design/evidence)
- **KB 数据**: `experiments/framework_driven_seed/data/seed_*.json` (97 records / 568 rows)
- **KB SQLite**: `experiments/framework_driven_seed/sqlite/{schema.sql, ingest.py, framework_seed.db (gitignored)}`
- **Pipeline 算法**: `process_calc/pipeline.py` (deterministic 470 行)
- **Pipeline 评估**: `experiments/pipeline_eval/` + `experiments/schema_eval/` + `experiments/pipeline_mvp/`
- **Public API**: `process_calc.calculate(method_id, **params)` (METHOD_REGISTRY 见 method_registry.py)

跨仓库写作: 实施代码 / 数据 / output 在本仓库; design.md / ledger.md / WO / evidence 在 ai-assistant 仓库 `Projects/process-expert/designs/`。

---

## 反 "AI 逃课" 行为契约 (forbidden practices)

研究/算法/数据/评估/报告全链条上, 以下"逃课"行为**绝对禁止**, 出现一次即视为该 WO 失败需重做。每条都有"在本项目的具体形态" + "触发该怎么办"。

### A — 评估 / 指标层面

#### A1 阈值后挪 (Goodhart goalpost shift)
**禁**: design.md 里写好的阈值 (e.g. `pipeline-eval design.md §6` 的 `friction>30%` / `coverage<50%` / schema-eval 的 `Δ≥5pp`), 一旦 commit, **任何 evidence/summary 不得修改**.
**触发时**: 测出来不达标, 老实写"未达标 X.Y%" + 提决策选项, 不动阈值.

#### A2 Cherry-pick run / 多跑选最好
**禁**: 同一份 trace / matrix / pipeline 跑 N 次只把最好的写进 evidence.
**约束**:
- runner 必须可重现 (no random sampling 没 seed)
- 每个 evidence 引用的数字必须来自 **deterministic 单次跑**
- 多次实验的 result 全部 commit 到 git, 不许只 commit 挑好的那次

#### A3 Hold-out 污染 / Trace 事后调
**禁**: 跑出来发现某条 query 没 pass, 改 trace 的 `expected` 让它 pass; 或事后改 query 的 SQL/kwargs 让结果好看.
**约束**:
- trace `expected` 列**只允许从教材/已有工艺卡抽取**, 不允许 LLM 起草 (Sean 不能审 LLM 起草的)
- 一旦 commit 进 git, 改 expected 必须有 git 记录 + evidence 写清"为什么改 + 改前指标 + 改后指标"
- ground truth (e.g. `test-files/falan/测试结果对照工艺卡.pdf`) 是只读资产

#### A4 Goodhart 代理指标 (优化 proxy 而非真目标)
**禁**: 为了让 coverage / accuracy / friction 数字好看, 拓宽 query / 放松 assess fn / 重定义指标定义.
**约束**:
- 评估指标定义一旦 commit 进 design.md, 不动
- 想改指标定义要起新 design 显式说明
- evidence 里所有数字必须有源 (run_trace.py output JSON 直引, 不许手敲数字)

### B — 算法 / 实现层面

#### B1 Hardcode 答案 + 谎称"识别能力"
**禁**: 把"已知正确答案"写进算法逻辑/字典, 让特定测试 case 看似通过, 但没有泛化能力, **同时**在 evidence 宣称"算法识别了 X".
**本项目形态**: `pipeline.py` 的 `_FEATURE_INTENT` / `_FALLBACKS` 字典就在这条边缘 — 它是 hardcode 12 种 feature.kind 的字典, enum 之外的特征会失败.
**约束**:
- 任何 hardcode 字典/规则**必须在代码注释 + design evidence 中显式标记** "这是过拟合风险, enum 之外失败"
- evidence 不得宣称"算法识别了 X" 当算法只是字典查表 — 要写"input 已声明特征类型 + 算法按字典分发"

#### B2 Bypass / Monkey-patch test
**禁**: test failed 时, 改 test 让它 pass; 删 assert; 用 `pytest.skip` / `xfail` 绕过; mock 掉真实 KB 调用让测试空跑.
**约束**:
- 测试 fail 必须改实现, 不改测试 (除非测试本身写错了, 修正后 evidence 写明)
- 不允许 mock 实际 KB 数据库 (我们就 568 行 / ~10MB, 没必要 mock)
- 不允许 `--no-verify` 跳过 pre-commit hooks 除非 Sean 显式授权

#### B3 吞异常 / silent fallback
**禁**: 用 `try: ... except: pass` 把所有错误吞掉, 让算法看起来"总是工作", 实际跑一半失败被静默.
**本项目形态**: pipeline.py 里 `_fill_cutting_params` / `_fill_allowance` 用了 `except Exception: pass` return None — **这是允许的边缘**, 仅限 KB lookup 路径.
**约束**:
- 仅在已知"无数据"的 KB lookup 路径允许 except + return None
- 必须把 None 计入 `gaps` 字段 (不能让上层以为查到数据)
- 不得在更高层用 try/except 把 invalid input / SQL bug / API 误用 一起吞掉
- 真正的异常必须 raise 出去, 让 runner / pytest 看到

#### B4 假装 deterministic 偷偷上 LLM
**禁**: design 写"deterministic 优先", 实际在算法关键路径里悄悄调 LLM 让数字好看.
**约束**:
- 任何 LLM 调用必须在 design.md 里**显式声明 LLM 介入点** (具体哪步 / 什么 prompt / 期望何种输出)
- 不得在 deterministic 模块里偷偷 import openai / anthropic / Skill('llm-*')
- evidence 里报数字时必须区分 "deterministic 路径 vs LLM 路径" 各贡献多少 query 的 pass

### C — 数据层面

#### C1 凭空造数据 (data fabrication)
**禁**: KB record 的 value_table 里写教材没有的数值, 凭"经验"或"合理推断"填.
**约束**:
- 每条 STD record 的 `source_doc` + `source_page` + `source_ref` 必须**指向教材/手册里实际存在的 cell**
- 若教材原 cell 字迹不清/缺失, value_table 用 `null` 不要猜
- 任何"推算/插值"必须 `quality_flags: ["inferred"]` + `extra_json` 写推算依据

#### C2 修数据修到 query 命中 (curve-fitting data to query)
**禁**: trace 跑出 no_data 后, 反过来"修补"原始 seed JSON 让特定 query 命中.
**本项目形态**: schema A/B/C 实验时给不锈钢 record 加 `material: "不锈钢"` 字段是**踩到边缘的合规修复** — 修真实 bug (record-level material 没传到 row-level), 不是凑数据.
**约束**:
- 修原始 seed JSON 必须先在 evidence 里说"这是数据 bug 还是 query 凑合"
- 给出"修复前 query 表现 + 修复后表现 + 修复理由"
- 不允许只为某条 query 加新字段而不影响其他 case

#### C3 选有利的 case
**禁**: 三例 hold-out 跑出来某例难看, 静默删了换一个让 evidence 好看.
**本项目固定 hold-out 集 (不可替换)**:
- falan (`test-files/falan/`)
- 定位销 (`test-files/定位销/`)
- 教材密封件定位套 (Ch3 §3.3.3, 表 3-91)
**约束**:
- 想加新 case 可以 (扩 hold-out 集, e.g. 教材另外 5 例)
- 不允许静默替换/删除现有 case
- 想换必须新 evidence 写"为什么换 + 旧 case 的最终指标 + git 记录"

### D — 报告层面

#### D1 避谈失败 / 用模糊表述掩饰 gap
**禁**: evidence 里只写"通过", 用"基本满足"/"接近目标"模糊掉真实数字.
**约束 — 每份 evidence 必须含三段**:
1. **实测数字直引** result JSON / pytest output / SQL count
2. **未达标 / 差距点** 段 (具体差多少 / 为什么差)
3. **下一步候选** 段 (≥2 个选项, 不只是单一推荐)

#### D2 改指标标签让差的进中性桶
**禁**: 改 outcome 4 桶 (`pass / partial / no_data / friction`) 的判定让 friction → partial 让数字好看.
**约束**:
- outcome 4 桶定义在 `pipeline-eval design.md §6` 写死, 不动
- 一条 query 怎么分桶必须由 trace 的 `assess` function 决定, 不允许 evidence 文档里"重新解读"
- 改 assess fn 必须在 git diff 里看得清, 跟改 expected 同样审计

#### D3 算法演示用人为简化的输入而不声明
**禁**: pipeline 演示用了简化 input, 但 evidence 不声明, 给读者"端到端"实际是"半自动"的错觉.
**本项目形态**: pipeline-mvp 的 input feature JSON 是手抽的, 跳过了 VLM/CAD 解析.
**约束**:
- pipeline 的 evidence 必须明说"输入预处理由谁完成 / 用何手段 / 跳过了哪些环节"
- 端到端 demo 必须列出"自动化覆盖范围 vs 人工准备范围"

### E — 项目特定

#### E1 用 KB hit rate 当 "工艺卡对错" 指标
**禁**: KB hit rate 高就宣称"算法工作". 真实目标是"产出可用的工艺规程", 不是 KB 命中率.
**约束**:
- 任何 evidence 不得用单一 KB hit rate 宣称算法成功
- 必须配 ground truth 工艺卡对比 + divergence 分析
- pipeline-eval 的 coverage 79.5% 跟 pipeline-mvp 的 KB hit rate 38% 是**两个不同维度**, 不可混淆

#### E2 三例 case 等同"全行业"
**禁**: 三例 (falan/定位销/textbook) 表现好就宣称 KB / pipeline 通用.
**约束 — 任何 design summary / evidence 必须含"边界声明"段**:
- "本结论的 generalization 限制是 N=3"
- 三例覆盖范围: 车削为主 + 加工中心铣 + 部分线切割; 304L/316L 不锈钢 + HT200 灰铸铁
- **不覆盖**: 磨削主导工艺 / 钣金 / 铸造 / 装配 / 特种加工 (电火花/激光/水切割) / 钛合金/高温合金 / 螺旋/齿轮/涡轮叶片型面

---

## 工作流契约 (跟 ai-assistant 仓库一致)

- **设计在 ai-assistant 仓库**: `Projects/process-expert/designs/YYYY-MM-DD-NN-{slug}/`
- **实施在本仓库**: `experiments/{slug}/` 或 `process_calc/` (公开 API)
- **PR per WO**: 每个 work order 一个独立 PR (e.g. `experiment/wo-005-cutting-params`); merge 后 main 上每条 commit 对应一个完成的 WO
- **可重现**: ingest.py / run_*.py 都必须 `python3 path/to/script.py` 直接跑通, 无 manual 前置步骤

## Test 契约

- `pytest tests/` 必须 100% 通过才能合 PR
- 新增 process_calc method 必须有教材原值测试 + 在 METHOD_REGISTRY 注册
- 现有 45 测试是回归基准, 不允许"我修了无关代码不小心改了行为, 测试随之改" — 测试改就要 evidence 说明

## Public API 兼容性

- `process_calc.calculate(method_id, **params)` 形状不变: 返回 `{result, unit, steps, formula, warnings, verified, implementation_status}`
- 内部 SQL / schema 可改 (schema_v2 已经改过一次), 但调用 method_id 的旧代码不能 break
- 加新 method_id 不算 break, 改/删旧 method_id 算 break — 跟 Sean 确认才动

---

## Git Convention

- Commit message: `type(scope): description` (feat/fix/docs/chore/feat)
- 不 amend / 不 force push / 不 push --force
- 跟 Sean 之前 saved 的 settings: `gh pr merge --rebase --delete-branch` 已授权 (settings.local.json)
- 重要变更 push 前先在 evidence 里写"为什么这么改"

## When in doubt

- 用 `WebSearch` / `WebFetch` 调研业内做法, 不要凭直觉
- 数据/算法选择不确定时, 设计实验对比不同选项 (`feedback_design_experiments_not_recommend.md` memory 已记)
- 不假装 Sean 是工艺专家可以审 LLM 起草内容; ground truth 必须来自教材/既有工艺卡
