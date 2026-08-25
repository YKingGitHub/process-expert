#!/usr/bin/env python3
"""Build a self-contained HTML report for the 33-part View Agent benchmark."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path


STATUS_ZH = {
    "STEP_EXPORTED": "STEP 已导出",
    "CAD_FAIL": "CAD 执行失败",
    "TECH_FAIL": "推理技术失败",
    "NOT_RUN": "未运行",
    "INVALID_RESULT": "结果损坏",
}


def escaped(value: object) -> str:
    return html.escape(str(value))


def number(value: object, digits: int = 2, empty: str = "—") -> str:
    if value is None:
        return empty
    return f"{float(value):,.{digits}f}"


def signed(value: object, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):+,.{digits}f}%"


def badge(status: str) -> str:
    css = "ok" if status == "STEP_EXPORTED" else "bad" if status.endswith("FAIL") else "muted"
    return f'<span class="badge {css}">{escaped(STATUS_ZH.get(status, status))}</span>'


def parse_evaluation(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("evaluation must use LABEL=PATH")
    label, path = value.split("=", 1)
    return label, Path(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference-manifest", type=Path, required=True)
    parser.add_argument("--ground-truth-manifest", type=Path, required=True)
    parser.add_argument("--evaluation", type=parse_evaluation, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    inference = json.loads(args.inference_manifest.read_text(encoding="utf-8"))
    truth_manifest = json.loads(args.ground_truth_manifest.read_text(encoding="utf-8"))
    truth_by_id = {sample["id"]: sample for sample in truth_manifest["samples"]}
    evaluations: list[dict[str, object]] = []
    for label, path in args.evaluation:
        payload = json.loads(path.read_text(encoding="utf-8"))
        failure_counts: dict[str, int] = {}
        first_attempt_exports = 0
        repaired_exports = 0
        for sample in payload["samples"]:
            result_path = path.parent / sample["id"] / "result.json"
            if not result_path.is_file():
                continue
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("status") == "STEP_EXPORTED":
                if len(result.get("attempts", [])) > 1:
                    repaired_exports += 1
                else:
                    first_attempt_exports += 1
            elif result.get("status") == "CAD_FAIL":
                error_type = str(result.get("execution", {}).get("error_type") or "OtherCadError")
                failure_counts[error_type] = failure_counts.get(error_type, 0) + 1
        evaluations.append(
            {
                "label": label,
                "path": str(path.resolve()),
                "summary": payload["summary"],
                "samples": {sample["id"]: sample for sample in payload["samples"]},
                "first_attempt_exports": first_attempt_exports,
                "repaired_exports": repaired_exports,
                "failure_counts": failure_counts,
            }
        )

    primary = evaluations[0]
    primary_summary = primary["summary"]
    measured_count = int(primary_summary["measured_count"])
    sample_count = int(primary_summary["sample_count"])
    export_rate = float(primary_summary["step_export_rate_pct"])
    median_volume = primary_summary["volume_abs_error_pct"]["median"]
    if measured_count:
        full_pass_count = int(primary_summary["geometry_pass_count"])
        conclusion = (
            f"主模型在 33 件中导出 {measured_count} 件有效 STEP（{export_rate:.1f}%）；"
            f"仅对成功导出的样本，体积绝对误差中位数为 {float(median_volume):.2f}%。"
            f"按三项阈值完整通过的只有 {full_pass_count}/33。"
            "这些数字必须同时看：未导出的样本不能从误差统计中消失。"
        )
    else:
        conclusion = "主模型未导出可测 STEP，因此当前不能给出有效的体积精度结论。"

    model_rows: list[str] = []
    for evaluation in evaluations:
        summary = evaluation["summary"]
        counts = summary["generation_status_counts"]
        model_rows.append(
            "<tr>"
            f"<td><strong>{escaped(evaluation['label'])}</strong><br><small>{escaped(Path(str(summary.get('model', ''))).name)}</small></td>"
            f"<td>{int(summary['measured_count'])} / {int(summary['sample_count'])}</td>"
            f"<td>{number(summary['step_export_rate_pct'], 1)}%</td>"
            f"<td>{int(counts.get('CAD_FAIL', 0))}</td>"
            f"<td>{int(counts.get('TECH_FAIL', 0))}</td>"
            f"<td>{int(evaluation['first_attempt_exports'])} / {int(evaluation['repaired_exports'])}</td>"
            f"<td>{number(summary['volume_abs_error_pct']['median'])}%</td>"
            f"<td>{number(summary['volume_abs_error_pct']['mean'])}%</td>"
            f"<td>{number(summary['volume_abs_error_pct']['p90'])}%</td>"
            f"<td>{int(summary['volume_pass_count'])}</td>"
            f"<td>{int(summary['geometry_pass_count'])}</td>"
            "</tr>"
        )

    failure_rows: list[str] = []
    for evaluation in evaluations:
        counts = evaluation["failure_counts"]
        distribution = "、".join(
            f"{escaped(error_type)} × {count}"
            for error_type, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ) or "无 CAD_FAIL"
        failure_rows.append(
            f"<tr><td><strong>{escaped(evaluation['label'])}</strong></td>"
            f"<td>{distribution}</td></tr>"
        )

    case_rows: list[str] = []
    for input_sample in inference["samples"]:
        case_id = input_sample["id"]
        truth = truth_by_id[case_id]["ground_truth_metrics"]
        cells = [
            f"<td><code>{escaped(case_id)}</code></td>",
            f"<td>{escaped(input_sample['name'])}<br><small>{len(input_sample['images'])} 张输入图</small></td>",
            f"<td class=\"num\">{number(truth['volume_mm3'], 1)}</td>",
        ]
        for evaluation in evaluations:
            row = evaluation["samples"].get(case_id, {})
            status = str(row.get("generation_status", "NOT_RUN"))
            cells.extend(
                [
                    f"<td>{badge(status)}</td>",
                    f"<td class=\"num\">{signed(row.get('volume_error_pct'))}</td>",
                    f"<td class=\"num\">{number(row.get('surface_area_abs_error_pct'))}%</td>",
                    f"<td class=\"num\">{number(row.get('bbox_max_abs_error_pct'))}%</td>",
                ]
            )
        case_rows.append("<tr>" + "".join(cells) + "</tr>")

    model_headers = "".join(
        f'<th colspan="4">{escaped(evaluation["label"])}</th>' for evaluation in evaluations
    )
    metric_headers = "".join(
        "<th>状态</th><th>体积偏差</th><th>面积绝对误差</th><th>包围盒最大误差</th>"
        for _ in evaluations
    )
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    thresholds = primary_summary["thresholds_pct"]
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>View Agent｜33 组单实体零件批量测试</title>
<style>
:root {{ --ink:#172033; --muted:#667085; --line:#d9dee8; --panel:#f7f9fc; --blue:#2457a6; --green:#16794b; --red:#b42318; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); background:white; font:15px/1.6 system-ui,-apple-system,"Segoe UI","PingFang SC",sans-serif; }}
main {{ width:min(1240px,calc(100% - 40px)); margin:0 auto; padding:48px 0 80px; }}
h1 {{ margin:0 0 8px; font-size:34px; line-height:1.25; }}
h2 {{ margin:44px 0 14px; font-size:23px; }}
p {{ margin:8px 0; }}
.meta, small {{ color:var(--muted); }}
.lead {{ max-width:900px; font-size:18px; }}
.cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:24px 0; }}
.card {{ border:1px solid var(--line); border-radius:8px; padding:16px; background:var(--panel); }}
.card b {{ display:block; color:var(--blue); font-size:27px; line-height:1.2; }}
.pipeline {{ display:grid; grid-template-columns:1fr 62px 1fr 62px 1fr; align-items:center; margin:20px 0; }}
.module {{ min-height:126px; padding:18px; border:2px solid var(--line); border-radius:8px; }}
.module.fixed {{ border-color:var(--blue); }}
.module h3 {{ margin:0 0 6px; }}
.arrow {{ text-align:center; color:var(--blue); font-size:30px; }}
.callout {{ border-left:4px solid var(--blue); background:#f3f7fd; padding:14px 18px; margin:18px 0; }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:8px; }}
table {{ width:100%; border-collapse:collapse; white-space:nowrap; }}
th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
th {{ background:#f1f4f9; font-size:13px; position:sticky; top:0; z-index:1; }}
tr:last-child td {{ border-bottom:0; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; background:#eef1f5; }}
.badge.ok {{ color:var(--green); background:#eaf8f1; }}
.badge.bad {{ color:var(--red); background:#fff0ee; }}
code {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }}
.foot {{ margin-top:34px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; }}
@media(max-width:850px) {{ .cards {{ grid-template-columns:1fr 1fr; }} .pipeline {{ grid-template-columns:1fr; gap:8px; }} .arrow {{ transform:rotate(90deg); }} }}
</style>
</head>
<body><main>
<p class="meta">固定几何提取器验证 · 生成于 {escaped(generated_at)}</p>
<h1>View Agent：33 组单实体零件批量测试</h1>
<p class="lead">本报告只回答第一环节能否从工程图稳定生成可验收的 STEP。真值 STEP 不进入推理，只在模型结束后由独立评测器读取。</p>

<div class="cards">
  <div class="card"><b>33</b>单实体零件</div>
  <div class="card"><b>39</b>工程图输入页</div>
  <div class="card"><b>{int(primary_summary['measured_count'])}</b>主模型有效 STEP</div>
  <div class="card"><b>{number(primary_summary['volume_abs_error_pct']['median'])}%</b>成功样本体积误差中位数</div>
</div>

<h2>测试边界：先把头和尾固定</h2>
<div class="pipeline">
  <div class="module fixed"><h3>① 几何提取器（本次被测）</h3><p>一张或多张工程图 → 参数化 CadQuery → STEP</p></div>
  <div class="arrow">→</div>
  <div class="module"><h3>② Workflow（暂不优化）</h3><p>只有当几何输入和验收信号可靠后，才进入工艺规程 workflow 优化。</p></div>
  <div class="arrow">→</div>
  <div class="module fixed"><h3>③ 独立验收器</h3><p>预测 STEP 与保留 GT 对比；统计体积、表面积和包围盒。</p></div>
</div>
<div class="callout"><strong>当前结论：</strong>{escaped(conclusion)}</div>

<h2>模型汇总</h2>
<div class="table-wrap"><table>
<thead><tr><th>模型</th><th>有效 STEP</th><th>导出率</th><th>CAD_FAIL</th><th>TECH_FAIL</th><th>首次 / 修复后成功</th><th>|体积误差|中位数</th><th>均值</th><th>P90</th><th>体积达标</th><th>三项全达标</th></tr></thead>
<tbody>{''.join(model_rows)}</tbody>
</table></div>
<p class="meta">阈值仅作为首轮工程基线：|体积误差| ≤ {number(thresholds['volume_abs'])}%，|表面积误差| ≤ {number(thresholds['surface_area_abs'])}%，包围盒三轴最大 |误差| ≤ {number(thresholds['bbox_axis_max_abs'])}%。误差统计分母只含可成功解析的预测 STEP，导出率单独报告。</p>

<h2>失败类型</h2>
<div class="table-wrap"><table><thead><tr><th>模型</th><th>最终一次 CAD 执行错误分布</th></tr></thead><tbody>{''.join(failure_rows)}</tbody></table></div>
<p class="meta"><code>UnsafeCadCode</code> 表示输出触发执行器安全规则；<code>NameError</code>、<code>AttributeError</code>、<code>ValueError</code> 等表示生成程序本身不可执行；OpenCascade 的 <code>StdFail_NotDone</code>、<code>Standard_Failure</code> 和 <code>Standard_ConstructionError</code> 表示几何构造失败。</p>

<h2>逐件结果</h2>
<div class="table-wrap"><table>
<thead><tr><th rowspan="2">编号</th><th rowspan="2">零件</th><th rowspan="2">GT 体积 mm³</th>{model_headers}</tr><tr>{metric_headers}</tr></thead>
<tbody>{''.join(case_rows)}</tbody>
</table></div>

<h2>数据与方法</h2>
<p>源压缩包共识别 70 组无歧义 PDF—STEP 配对。OpenCascade 逐件读取后，保留 33 组单实体，排除 37 组多实体/装配体；30 组按同目录同名配对，3 组按唯一零件号合并多张图纸。输入共 39 张 200 DPI 图像。</p>
<p>每个模型在一个 GPU 作业内只加载一次；每件先生成 CadQuery，经过 AST 白名单检查后在独立 CAD Python 环境执行，首次失败允许模型修复一次。最终由独立进程读取 GT 和预测 STEP，按方向无关的排序包围盒尺寸计分。</p>
<p>压缩包 SHA-256：<code>{escaped(inference['archive_sha256'])}</code></p>

<div class="foot">离线单文件报告。原始逐件 JSON/CSV 保留在集群运行目录；本页不包含源图纸或 GT STEP。</div>
</main></body></html>
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
