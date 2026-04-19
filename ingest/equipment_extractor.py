"""Equipment extractor — extracts structured equipment specification data from equipment_specs pages."""

import json
import os
from datetime import datetime

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown

SYSTEM_PROMPT = """你是设备规格参数提取器。从以下 Markdown 表格中提取所有设备规格记录。

典型表格结构：
- 设备类型（如"车床"、"铣床"、"磨床"）
- 型号（如"CA6140"、"X6132"）
- 技术参数（如"最大加工直径"、"主轴转速范围"）

每条记录包含:
- equipment_type: 设备类型（如"车床"、"铣床"、"磨床"），尽量从上下文推断
- model_number: 设备型号（如"CA6140"），若无明确型号则为 null
- param_name: 参数名称（如"最大加工直径"、"主轴转速范围"），不得为空
- param_value: 参数值（如"400"、"10~1400"），保留原始格式
- param_unit: 参数单位（如"mm"、"r/min"），无则为 null
- table_ref: 表格编号（如"表4-15"），若无明确编号则用页码格式 "P{N}"，不得为空
- chapter: 章节名（从上下文推断，无法推断则用""）

【关键规则】
1. param_name 不得为空，必须从表格列标题或行标题提取
2. 同一设备有多个参数时，每个参数生成独立记录
3. 如果表格包含多个设备型号，每个型号的每个参数都生成独立记录
4. equipment_type 尽量归类到标准类型（车床、铣床、磨床、钻床、刨床、镗床等）

返回 JSON: {"equipment": [...], "source_page": N}
若该页无可提取设备规格数据，返回 {"equipment": [], "source_page": N}"""


def extract_equipment(page: PageMarkdown, client) -> list[dict]:
    """从 equipment_specs 页面提取设备规格记录列表。返回 raw dict 列表。"""
    user_content = f"--- Page {page.page_num} ---\n{page.markdown_text}"
    try:
        result, finish_reason = chat_json(
            client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=4096
        )
        if finish_reason != "stop":
            print(f"[equipment_extractor] Page {page.page_num} output truncated (finish_reason={finish_reason})")

        equipment = result.get("equipment", [])
        source_page = result.get("source_page", page.page_num)

        for e in equipment:
            e["source_page"] = source_page
            # table_ref fallback
            if not e.get("table_ref", "").strip() or e.get("table_ref") in ("未标注", "无", ""):
                e["table_ref"] = f"P{source_page}"
            # Strip whitespace from key fields
            for key in ("equipment_type", "model_number", "param_name", "param_value", "param_unit"):
                if e.get(key):
                    e[key] = e[key].strip()

        # Save raw results to output/ (ADR-6)
        _save_raw(equipment, page.page_num)
        return equipment
    except Exception as e:
        print(f"[equipment_extractor] Page {page.page_num} failed: {e}")
        return []


def _save_raw(records: list[dict], page_num: int) -> None:
    """Save raw extraction results to JSONL for auditing."""
    try:
        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("output", f"equipment_raw_{ts}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Non-critical
