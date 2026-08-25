# View Agent（图纸 → CadQuery → STEP）

这里是几何提取器的可运行入口。它把一张或多张工程图交给 Qwen3-VL，生成 CadQuery 程序，并在通过本地安全检查后导出 STEP。

当前定位必须说清楚：

- `Qwen/Qwen3-VL-8B-Instruct` 是 Ortho2CAD 的基座，只用于跑通环境和建立基线。
- Ortho2CAD 论文模型的 SFT/RL 权重截至本次核查尚未在官方仓库公开，不能把基座测试结果当作 Ortho2CAD 结果。
- SOV-CAD 官方仓库同样尚未提供预训练权重，因此当前主线先采用 Ortho2CAD 的“图纸 → CadQuery → STEP”接口。
- 本地 A40 实测已经跑通 8B 基座到 STEP，但法兰预测体积仍偏 `+11.34%`；提高图像分辨率能改善尺寸读取，仍不能解决尺寸到特征的归位。当前实现是可复现实验基线，不是已经合格的固定几何提取器，详见 `SMOKE_RESULTS.md`。
- 生成程序由独立 Python 环境执行；`cad_executor.py` 会做 AST 白名单检查并拒绝文件、网络、子进程和私有属性访问等危险代码。它是面向本项目输入的风险收敛层，不应被视为可执行任意恶意代码的系统级沙箱。
- 图像预处理默认限制在 256--1280 个 `28×28` 像素单元之间，也可通过环境变量提高上限；默认设置把端盖图的输入从约 7,500 个 token 降至约 1,000 个，适合先做单卡冒烟测试。

## 目录

```text
view_agent/
├── view_agent.py              # GPU 推理入口
├── prepare_batch.py           # 构建输入/GT 隔离的 33 件评测集
├── batch_view_agent.py        # 单次加载模型的断点续跑批处理
├── evaluate_batch.py          # 独立 STEP 几何评测
├── build_batch_report.py      # 生成离线单文件 HTML 报告
├── cad_executor.py            # CadQuery 安全执行与 STEP 导出
├── check_env.py               # CPU/GPU、模型和 CadQuery 环境检查
├── download_qwen_model.sh     # ModelScope 断点续传与 SHA-256 校验
├── SMOKE_RESULTS.md           # A40 真实图纸冒烟结果与能力边界
├── requirements-smoke.txt     # 单卡冒烟环境依赖
├── requirements-cad.txt       # 独立 STEP 导出环境依赖
└── slurm/
    ├── gpu_shell.sh           # 交互式申请 GPU
    ├── run_debug.sh           # 30 分钟 A40 冒烟测试
    ├── submit_batch.sbatch    # 33 件批量推理和事后评测
    └── submit_smoke.sbatch    # A800 正式单卡作业
```

## 当前集群环境

本机已创建以下共享路径：

```text
Python: /hpc2hdd/home/lwang592/projects/.venvs/process-view-agent/bin/python
CAD:    /hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python
Model:  /hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-8B-Instruct
Cache:  /hpc2hdd/home/lwang592/projects/.cache/huggingface
```

本次环境固定的上游版本为：Ortho2CAD `6ea7eef388745e8bc255296d37f210ead02737fc`；2B 技术冒烟模型 revision `89644892e4d85e24eaac8bacfd4f463576704203`；8B 目标基座 revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`。

登录节点看不到 GPU；必须先通过 Slurm 分配。当前集群每张 GPU 最多配 8 个 CPU 核，因此不能沿用旧的 `--cpus-per-task=16` 模板。

模型下载可断点续传，并在完成后校验官方仓库给出的 SHA-256：

```bash
bash geometry-training-handoff/view_agent/download_qwen_model.sh \
  Qwen3-VL-8B-Instruct
```

## 环境检查

CPU 侧检查：

```bash
/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent/bin/python \
  geometry-training-handoff/view_agent/check_env.py
```

GPU 侧检查：

```bash
bash geometry-training-handoff/view_agent/slurm/gpu_shell.sh debug
/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent/bin/python \
  geometry-training-handoff/view_agent/check_env.py --require-cuda
```

## 单件冒烟测试

`debug` 分区最多 30 分钟，适合验证模型加载与短输出：

```bash
bash geometry-training-handoff/view_agent/slurm/run_debug.sh \
  geometry-training-handoff/drawings/端盖.png \
  geometry-training-handoff/view_agent/runs/end_cover_smoke
```

可通过环境变量切换技术冒烟模型和输出长度，例如：

```bash
VIEW_AGENT_MODEL=/hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-2B-Instruct \
VIEW_AGENT_MAX_NEW_TOKENS=1024 \
bash geometry-training-handoff/view_agent/slurm/run_debug.sh
```

扫描图尺寸较小、需要提高视觉预算时，可设置：

```bash
VIEW_AGENT_MAX_PIXELS=2007040 \
bash geometry-training-handoff/view_agent/slurm/run_debug.sh \
  geometry-training-handoff/drawings/法兰.png \
  geometry-training-handoff/view_agent/runs/flange-highres
```

长期 A800 作业：

```bash
sbatch geometry-training-handoff/view_agent/slurm/submit_smoke.sbatch \
  geometry-training-handoff/drawings/端盖.png \
  geometry-training-handoff/view_agent/runs/end_cover_a800
```

输出目录包含：

```text
generated_cadquery.py   # 模型原始 CadQuery 程序
generated_cadquery_repair_1.py  # 首次执行失败时的自动修复版本
generated.step          # 程序执行成功时产生
result.json             # 模型、耗时、状态、错误分类和产物路径
```

## 接入论文权重

论文权重公开后无需改接口，只需把模型路径换掉：

```bash
export VIEW_AGENT_MODEL=/path/to/ortho2cad/checkpoint
```

建议固定两条评测线：

1. 基座线：`Qwen3-VL-8B-Instruct`，衡量通用 VLM 的起点。
2. 专项线：Ortho2CAD SFT/RL checkpoint，衡量专项训练的增益。

两条线都必须用同一组图纸、同一执行器和同一几何验收器，且真值 STEP 只用于事后记分，不能回喂给 View Agent。

## 33 件单实体批量基线

数据准备脚本先检查全部无歧义 PDF—STEP 配对，再用 OpenCascade 只保留有效单实体。它生成两个物理独立的清单：推理入口只接受 `inference_manifest.json`，并会拒绝任何 GT 字段；`evaluation_manifest.json` 仅由模型退出后的 CAD 评测进程读取。

```bash
CAD=/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python
DATA=/hpc2hdd/home/lwang592/projects/.cache/process-expert/drawing_20260810_single

XDG_CACHE_HOME=/hpc2hdd/home/lwang592/projects/.cache "$CAD" \
  geometry-training-handoff/view_agent/prepare_batch.py \
  --archive 图纸20260810.zip \
  --output-dir "$DATA"
```

正式作业会一次加载模型、逐件落盘，因此被抢占或超时后可直接重提并从已有 `result.json` 继续：

```bash
sbatch geometry-training-handoff/view_agent/slurm/submit_batch.sbatch \
  /hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-8B-Instruct \
  geometry-training-handoff/view_agent/runs/batch_20260810_qwen3vl8b \
  "$DATA/inference_manifest.json" \
  "$DATA/evaluation_manifest.json"
```

评测同时报告 STEP 有效导出率与成功样本的体积、表面积、方向无关包围盒误差，不能只用成功子集的平均误差代表全体能力。首轮阈值为体积绝对误差 2%、表面积绝对误差 5%、包围盒三轴最大绝对误差 2%。

## 上游资料

- [Ortho2CAD 论文](https://arxiv.org/abs/2607.08891) / [官方代码](https://github.com/AdityaJoglekar/Ortho2CAD)
- [SOV-CAD 论文](https://arxiv.org/abs/2607.04119) / [官方代码](https://github.com/LukePhong/SOV-CAD)
- [Qwen3-VL-8B-Instruct 基座](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
