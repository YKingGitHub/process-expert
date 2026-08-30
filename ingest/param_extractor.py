"""Parameter extractor — extracts structured process params from param_table pages."""

import json

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown

SYSTEM_PROMPT = """你是金属切削工艺参数提取器。从以下 Markdown 表格中提取所有参数记录。
每条记录包含:
- operation_type: 工序（如"精车"、"粗铣"），从表格标题或上下文推断
- material_grade: 材料（如"45钢"、"HT200"），若表格未区分材料则用"通用"
- parameter_name: 参数名（如"切削速度"、"进给量"、"背吃刀量"）
- value: 数值（仅数字或范围，如"150"、"0.1~0.2"，不含单位）
- unit: 单位（如"m/min"、"mm/r"、"mm"）
- conditions: 其他条件（JSON object 字符串，如{"模数":"5","精度等级":"6"}，无条件则为"{}"）
- table_ref: 表格编号（如"表4-15"），若无明确编号则用页码格式 "P{N}"（如"P42"），不得为空字符串或"未标注"
- chapter: 章节名（从上下文推断，无法推断则用""）

返回 JSON: {"params": [...], "source_page": N}
若该页无可提取参数，返回 {"params": [], "source_page": N}"""


def extract_params(page: PageMarkdown, client) -> list[dict]:
    """从 param_table 页面提取参数记录列表。返回 raw dict 列表（含 source_page）。"""
    user_content = f"--- Page {page.page_num} ---\n{page.markdown_text}"
    try:
        result, finish_reason = chat_json(client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=4096)
        params = result.get("params", [])
        source_page = result.get("source_page", page.page_num)
        # 附加 source_page 到每条记录
        for p in params:
            p["source_page"] = source_page
            # 如果 table_ref 为空或"未标注"，替换为页码格式
            if not p.get("table_ref", "").strip() or p.get("table_ref") in ("未标注", "无"):
                p["table_ref"] = f"P{source_page}"
            # conditions 保证是合法 JSON 字符串
            conditions = p.get("conditions", {})
            if isinstance(conditions, dict):
                p["conditions"] = json.dumps(conditions, ensure_ascii=False)
            elif not isinstance(conditions, str):
                p["conditions"] = "{}"
        return params
    except Exception as e:
        print(f"[param_extractor] Page {page.page_num} failed: {e}")
        return []
