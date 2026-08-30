"""Page classifier — rule-based pre-classification + LLM 7-class fallback."""

import re

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown

BATCH_SIZE = 10

VALID_TYPES = {
    "cutting_params", "tolerance_fits", "equipment_specs",
    "surface_standards", "unit_conversion", "knowledge_table", "plain_text",
}

SYSTEM_PROMPT = """你是工艺手册页面分类器。每页 Markdown 分七类:
- cutting_params: 专指切削加工工艺参数表——必须包含切削速度(Vc)、进给量(f)、背吃刀量(ap)、切削深度、余量等切削加工参数。注意：螺纹尺寸表、几何尺寸表、零件结构尺寸表不属于此类
- tolerance_fits: 公差与配合表格（公差等级、偏差值、配合代号如 H7/h6）
- equipment_specs: 设备/机床规格参数表（型号、功率、主轴转速、工作台尺寸等）
- surface_standards: 表面粗糙度/光洁度标准表（Ra、Rz 值与加工方法对应关系）
- unit_conversion: 单位换算表（英制/公制换算、磅/千克等）
- knowledge_table: 其他含表格的页面，包括：螺纹尺寸参数表、零件结构尺寸表、夹具结构尺寸表、工艺规则表、材料性能表等
- plain_text: 纯文字段落，无表格

判断优先级：如果一个页面同时包含多类表格，取主要内容类型（占页面面积最大的表格类型）。cutting_params 仅限于切削工艺参数（速度、进给、切深），其他数值表格归 knowledge_table。

返回 JSON: {"classifications": [{"page_num": N, "type": "..."}]}
每个 page_num 必须对应输入中的页码，type 只能是以上七个值之一。"""


def extract_table_headers(markdown: str) -> str:
    """提取 Markdown 表格的表头行（前 1-2 行），转小写。"""
    lines = markdown.split('\n')
    headers = []
    for line in lines:
        stripped = line.strip()
        if '|' in stripped and not re.match(r'^[\s|:-]+$', stripped):
            headers.append(stripped.lower())
        elif headers and re.match(r'^[\s|:-]+$', stripped):
            # separator line after header — skip it
            continue
        elif headers:
            # stop after header block
            break
    return ' '.join(headers)


def rule_based_preclassify(markdown: str) -> str | None:
    """基于表头关键词的确定性预分类。返回 page_type 或 None。"""
    headers = extract_table_headers(markdown).lower()
    if not headers:
        return None
    # surface_standards 优先于 tolerance_fits（Ra/Rz 是更强信号，避免"配合"误匹配）
    if any(kw in headers for kw in ['ra', 'rz', '粗糙度']):
        return 'surface_standards'
    if any(kw in headers for kw in ['h7', 'h6', 'it', '公差等级', '偏差', '公差配合']):
        return 'tolerance_fits'
    if any(kw in headers for kw in ['型号', '功率', 'kw', '主轴转速', '工作台']):
        return 'equipment_specs'
    if any(kw in headers for kw in ['换算', 'inch', '英寸', '磅']):
        return 'unit_conversion'
    if any(kw in headers for kw in ['切削速度', '进给量', '背吃刀量', 'vc', 'ap']):
        return 'cutting_params'
    return None


def classify_pages(pages: list[PageMarkdown], client) -> list[PageMarkdown]:
    """混合分类：先规则预分类，未命中的走 LLM 7 类分类。"""
    page_map = {p.page_num: p for p in pages}
    rule_hit = 0
    unclassified = []

    # Phase 1: rule-based pre-classification
    for p in pages:
        result = rule_based_preclassify(p.markdown_text)
        if result:
            p.page_type = result
            rule_hit += 1
        else:
            unclassified.append(p)

    print(f"[page_classifier] Rule-based: {rule_hit}/{len(pages)} pages classified "
          f"({len(unclassified)} remaining for LLM)")

    # Phase 2: LLM classification for unclassified pages
    for batch_start in range(0, len(unclassified), BATCH_SIZE):
        batch = unclassified[batch_start:batch_start + BATCH_SIZE]
        user_content = _build_batch_prompt(batch)
        try:
            result, _ = chat_json(client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=1024)
            for item in result.get("classifications", []):
                pnum = item.get("page_num")
                ptype = item.get("type", "plain_text")
                if pnum in page_map and ptype in VALID_TYPES:
                    page_map[pnum].page_type = ptype
        except Exception as e:
            for p in batch:
                if p.page_type == "unknown":
                    p.page_type = "plain_text"
            print(f"[page_classifier] LLM batch {batch_start // BATCH_SIZE} failed: {e}")

    # Fallback: remaining unknown → plain_text
    for p in pages:
        if p.page_type == "unknown":
            p.page_type = "plain_text"

    return pages


def _build_batch_prompt(batch: list[PageMarkdown]) -> str:
    parts = []
    for p in batch:
        preview = p.markdown_text[:800]
        parts.append(f"--- Page {p.page_num} ---\n{preview}")
    return "\n\n".join(parts)
