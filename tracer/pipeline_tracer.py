"""
Pipeline Tracer — 工艺卡生成管线全程追踪日志

每个 Stage 记录: 输入摘要、推理过程、搜索记录、输出摘要、耗时
最终输出: JSON trace + Markdown 可读报告
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class PipelineTracer:
    def __init__(self):
        self.run_id: str = ""
        self.start_time: float = 0
        self.end_time: float = 0
        self.input_summary: str = ""
        self.stages: list[dict] = []
        self._current_stage: Optional[dict] = None

    def start(self, run_id: str, input_summary: str):
        self.run_id = run_id
        self.start_time = time.time()
        self.input_summary = input_summary
        self.stages = []

    def begin_stage(self, name: str, input_data: Any = None):
        if self._current_stage is not None:
            self._end_current_stage(None)
        self._current_stage = {
            "name": name,
            "start_time": time.time(),
            "input": _summarize(input_data),
            "reasoning": [],
            "searches": [],
            "output": None,
            "error": None,
            "duration_ms": 0,
        }

    def log_reasoning(self, text: str):
        if self._current_stage:
            self._current_stage["reasoning"].append(text)

    def log_search_result(self, source: str, query: str, results_summary: str):
        if self._current_stage:
            self._current_stage["searches"].append({
                "source": source,
                "query": query,
                "results": results_summary,
            })

    def log_error(self, error: str):
        if self._current_stage:
            self._current_stage["error"] = error

    def end_stage(self, output_data: Any = None):
        self._end_current_stage(output_data)

    def _end_current_stage(self, output_data: Any):
        if self._current_stage is None:
            return
        self._current_stage["output"] = _summarize(output_data)
        self._current_stage["duration_ms"] = int(
            (time.time() - self._current_stage["start_time"]) * 1000
        )
        del self._current_stage["start_time"]
        self.stages.append(self._current_stage)
        self._current_stage = None

    def finish(self, output_dir: str = "output") -> tuple[str, str]:
        if self._current_stage is not None:
            self._end_current_stage(None)
        self.end_time = time.time()

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = out / f"trace_{ts}.json"
        md_path = out / f"trace_{ts}.md"

        trace = self._to_dict()
        json_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2))
        md_path.write_text(self._to_markdown(trace))

        return str(json_path), str(md_path)

    def _to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "input_summary": self.input_summary,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
            "total_duration_ms": int((self.end_time - self.start_time) * 1000),
            "stages": self.stages,
        }

    def _to_markdown(self, trace: dict) -> str:
        lines = [
            f"# 工艺卡生成 Trace 报告",
            f"",
            f"- **Run ID**: {trace['run_id']}",
            f"- **开始时间**: {trace['start_time']}",
            f"- **结束时间**: {trace['end_time']}",
            f"- **总耗时**: {trace['total_duration_ms']}ms",
            f"- **输入**: {trace['input_summary']}",
            f"",
        ]

        for i, stage in enumerate(trace["stages"], 1):
            status = "ERROR" if stage.get("error") else "OK"
            lines.append(f"---")
            lines.append(f"")
            lines.append(f"## Stage {i}: {stage['name']} [{status}] ({stage['duration_ms']}ms)")
            lines.append(f"")

            if stage.get("input"):
                lines.append(f"### 输入")
                lines.append(f"```")
                lines.append(_truncate(stage["input"], 500))
                lines.append(f"```")
                lines.append(f"")

            if stage.get("reasoning"):
                lines.append(f"### 推理过程")
                for r in stage["reasoning"]:
                    lines.append(f"- {r}")
                lines.append(f"")

            if stage.get("searches"):
                lines.append(f"### 搜索记录")
                for s in stage["searches"]:
                    lines.append(f"- **{s['source']}** | 查询: `{s['query']}`")
                    lines.append(f"  结果: {s['results']}")
                lines.append(f"")

            if stage.get("error"):
                lines.append(f"### 错误")
                lines.append(f"```")
                lines.append(stage["error"])
                lines.append(f"```")
                lines.append(f"")

            if stage.get("output"):
                lines.append(f"### 输出")
                lines.append(f"```")
                lines.append(_truncate(stage["output"], 1000))
                lines.append(f"```")
                lines.append(f"")

        return "\n".join(lines)


def _summarize(data: Any) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(data)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... (truncated, {len(text)} chars total)"
