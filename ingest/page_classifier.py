"""Page classifier — LLM-based classification of PDF pages into content types."""

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown

BATCH_SIZE = 10

SYSTEM_PROMPT = """你是工艺手册页面分类器。每页 Markdown 分三类:
- param_table: 含数值参数的表格（如切削速度表、余量表、进给量表）
- knowledge_table: 含工艺规则/影响因素/经验描述的表格（文字为主，参数为辅）
- plain_text: 纯文字段落，无表格

返回 JSON: {"classifications": [{"page_num": N, "type": "..."}]}
每个 page_num 必须对应输入中的页码，type 只能是以上三个值之一。"""


def classify_pages(pages: list[PageMarkdown], client) -> list[PageMarkdown]:
    """批量分类页面（每批 10 页），更新并返回 page_type。"""
    page_map = {p.page_num: p for p in pages}

    for batch_start in range(0, len(pages), BATCH_SIZE):
        batch = pages[batch_start:batch_start + BATCH_SIZE]
        user_content = _build_batch_prompt(batch)
        try:
            result = chat_json(client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=1024)
            for item in result.get("classifications", []):
                pnum = item.get("page_num")
                ptype = item.get("type", "plain_text")
                if pnum in page_map and ptype in ("param_table", "knowledge_table", "plain_text"):
                    page_map[pnum].page_type = ptype
        except Exception as e:
            # 批次失败 — 降级为 plain_text
            for p in batch:
                if p.page_type == "unknown":
                    p.page_type = "plain_text"
            print(f"[page_classifier] Batch {batch_start//BATCH_SIZE} failed: {e}")

    # 未分类的页面默认 plain_text
    for p in pages:
        if p.page_type == "unknown":
            p.page_type = "plain_text"

    return pages


def _build_batch_prompt(batch: list[PageMarkdown]) -> str:
    parts = []
    for p in batch:
        preview = p.markdown_text[:800]  # 每页最多 800 字符
        parts.append(f"--- Page {p.page_num} ---\n{preview}")
    return "\n\n".join(parts)
