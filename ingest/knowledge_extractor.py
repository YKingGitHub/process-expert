"""Knowledge extractor — extracts KnowledgeChunk records from knowledge_table pages."""

from ingest.llm_client import chat_json
from ingest.schemas import KnowledgeChunk, PageMarkdown

SYSTEM_PROMPT = """你是工艺知识提取器。从以下工艺手册页面提取工艺规则、经验描述和影响因素记录。
每条记录包含:
- content: 完整的知识内容（保留原文，不要截断）
- chapter: 章节名（从上下文推断，无法推断则用""）

返回 JSON: {"chunks": [{"content": "...", "chapter": "..."}], "source_page": N}
若无可提取内容，返回 {"chunks": [], "source_page": N}"""

SOURCE_NAME = "工艺知识库"


def extract_knowledge(page: PageMarkdown, client) -> list[KnowledgeChunk]:
    """从 knowledge_table 页面提取知识块列表。"""
    user_content = f"--- Page {page.page_num} ---\n{page.markdown_text}"
    try:
        result, _ = chat_json(client, "qwen3.5-plus", SYSTEM_PROMPT, user_content, max_tokens=4096)
        chunks = result.get("chunks", [])
        source_page = result.get("source_page", page.page_num)
        return [
            KnowledgeChunk(
                content=c.get("content", ""),
                source_page=source_page,
                chapter=c.get("chapter", ""),
                source=SOURCE_NAME,
            )
            for c in chunks if c.get("content", "").strip()
        ]
    except Exception as e:
        print(f"[knowledge_extractor] Page {page.page_num} failed: {e}")
        return []
