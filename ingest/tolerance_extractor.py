"""Tolerance extractor — extracts structured tolerance fit data from tolerance_fits pages."""

import json
import os
from datetime import datetime

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown

SYSTEM_PROMPT = """你是公差配合参数提取器。从以下 Markdown 表格中提取所有公差配合记录。

典型表格结构：
- 行 = 尺寸段（如"大于30至50"、">30~50"），解析为 nominal_min 和 nominal_max
- 列 = 公差代号（如 H7、f6、JS9），即 fit_code
- 值 = 偏差值（上偏差/下偏差，单位可能为 μm 或 mm）

每条记录包含:
- nominal_min: 尺寸段下限（mm），如 30
- nominal_max: 尺寸段上限（mm），如 50。nominal_max 必须 > nominal_min
- fit_code: 公差代号，保留原始大小写（ISO 286：大写=孔公差如H7，小写=轴公差如f6），去除空格，不含中文
- fit_type: "基孔制"、"基轴制" 或 null（从表格标题/上下文推断）
- upper_deviation: 上偏差（mm）。若原文单位为 μm，必须÷1000 转为 mm（如 +25μm → 0.025）
- lower_deviation: 下偏差（mm）。若原文单位为 μm，必须÷1000 转为 mm（如 -25μm → -0.025）
- tolerance_grade: 公差等级（如"IT7"），从表格标题或上下文推断，无法推断则为 null
- standard_ref: 标准引用（如"GB/T 1801"），无法推断则为 null
- table_ref: 表格编号（如"表4-15"），若无明确编号则用页码格式 "P{N}"，不得为空
- chapter: 章节名（从上下文推断，无法推断则用""）

【关键规则】
1. 每个尺寸段+公差代号的交叉单元格生成一条独立记录
2. 偏差值统一输出 mm。判断方法：若数值绝对值 ≥1（如 +25、-13），几乎一定是 μm，必须÷1000
3. fit_code 只保留字母+数字（如 H7、f6、JS9），不含中文、括号、空格
4. 多列宽表必须逐列提取，不能只取前几列
5. 合并单元格的尺寸段适用于所有子行

返回 JSON: {"tolerances": [...], "source_page": N}
若该页无可提取公差数据，返回 {"tolerances": [], "source_page": N}"""


def extract_tolerance(page: PageMarkdown, client) -> list[dict]:
    """从 tolerance_fits 页面提取公差配合记录列表。返回 raw dict 列表。"""
    user_content = f"--- Page {page.page_num} ---\n{page.markdown_text}"
    try:
        result, finish_reason = chat_json(
            client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=32768
        )
        if finish_reason != "stop":
            print(f"[tolerance_extractor] Page {page.page_num} output truncated (finish_reason={finish_reason})")

        tolerances = result.get("tolerances", [])
        source_page = result.get("source_page", page.page_num)

        for t in tolerances:
            t["source_page"] = source_page
            # table_ref fallback
            if not t.get("table_ref", "").strip() or t.get("table_ref") in ("未标注", "无", ""):
                t["table_ref"] = f"P{source_page}"
            # fit_code strip
            if t.get("fit_code"):
                t["fit_code"] = t["fit_code"].strip()
            # Deviation type conversion (ensure float)
            for key in ("upper_deviation", "lower_deviation", "nominal_min", "nominal_max"):
                if t.get(key) is not None:
                    try:
                        t[key] = float(t[key])
                    except (ValueError, TypeError):
                        t[key] = None

        # Save raw results to output/ (ADR-6)
        _save_raw(tolerances, page.page_num)
        return tolerances
    except Exception as e:
        print(f"[tolerance_extractor] Page {page.page_num} failed: {e}")
        return []


def _save_raw(records: list[dict], page_num: int) -> None:
    """Save raw extraction results to JSONL for auditing."""
    try:
        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("output", f"tolerance_raw_{ts}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Non-critical — don't fail extraction on I/O error
