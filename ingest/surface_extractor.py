"""Surface extractor — extracts structured surface roughness data from surface_standards pages."""

import json
import os
from datetime import datetime

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown

SYSTEM_PROMPT = """你是表面粗糙度参数提取器。从以下 Markdown 表格中提取所有表面粗糙度记录。

典型表格结构：
- 行 = 加工方法（如"精车"、"粗磨"、"研磨"）
- 列 = Ra/Rz 范围

每条记录包含:
- machining_method: 加工方法（如"精车"、"粗铣"、"外圆磨"），不得为空
- process_condition: 加工条件/备注（如"用金刚石刀"、"低速"），无则为 null
- ra_min: Ra 最小值（μm），如 0.8。"0.8~3.2" → ra_min=0.8
- ra_max: Ra 最大值（μm），如 3.2。"0.8~3.2" → ra_max=3.2。单值时 ra_min=ra_max
- rz_min: Rz 最小值（μm），无则为 null
- rz_max: Rz 最大值（μm），无则为 null
- applicable_material: 适用材料（如"钢"、"铸铁"），无法推断则为 null
- standard_ref: 标准引用（如"GB/T 1031"），无法推断则为 null
- table_ref: 表格编号（如"表4-15"），若无明确编号则用页码格式 "P{N}"，不得为空
- chapter: 章节名（从上下文推断，无法推断则用""）

【关键规则】
1. machining_method 不得为空，必须从表格行标题提取
2. Ra/Rz 范围解析："0.8~3.2" → min=0.8, max=3.2；单值"1.6" → min=1.6, max=1.6
3. 同一加工方法有多种条件时，每种条件生成独立记录
4. ra_min 和 ra_max 至少有一个不为 null

返回 JSON: {"surfaces": [...], "source_page": N}
若该页无可提取粗糙度数据，返回 {"surfaces": [], "source_page": N}"""


def extract_surface(page: PageMarkdown, client) -> list[dict]:
    """从 surface_standards 页面提取表面粗糙度记录列表。返回 raw dict 列表。"""
    user_content = f"--- Page {page.page_num} ---\n{page.markdown_text}"
    try:
        result, finish_reason = chat_json(
            client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=4096
        )
        if finish_reason != "stop":
            print(f"[surface_extractor] Page {page.page_num} output truncated (finish_reason={finish_reason})")

        surfaces = result.get("surfaces", [])
        source_page = result.get("source_page", page.page_num)

        for s in surfaces:
            s["source_page"] = source_page
            # table_ref fallback
            if not s.get("table_ref", "").strip() or s.get("table_ref") in ("未标注", "无", ""):
                s["table_ref"] = f"P{source_page}"
            # machining_method strip
            if s.get("machining_method"):
                s["machining_method"] = s["machining_method"].strip()
            # Numeric type conversion
            for key in ("ra_min", "ra_max", "rz_min", "rz_max"):
                if s.get(key) is not None:
                    try:
                        s[key] = float(s[key])
                    except (ValueError, TypeError):
                        s[key] = None

        # Save raw results to output/ (ADR-6)
        _save_raw(surfaces, page.page_num)
        return surfaces
    except Exception as e:
        print(f"[surface_extractor] Page {page.page_num} failed: {e}")
        return []


def _save_raw(records: list[dict], page_num: int) -> None:
    """Save raw extraction results to JSONL for auditing."""
    try:
        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("output", f"surface_raw_{ts}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Non-critical
