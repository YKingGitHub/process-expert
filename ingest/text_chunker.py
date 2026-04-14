"""Text chunker — deterministic sliding-window chunking for plain_text pages."""

from ingest.schemas import KnowledgeChunk

SOURCE_NAME = "工艺知识库"


def chunk_text(text: str, source_page: int, chapter: str = "",
               chunk_size: int = 500, overlap: int = 100) -> list[KnowledgeChunk]:
    """
    Deterministic sliding-window chunking. No LLM calls.

    Returns list of KnowledgeChunk. For text of length L:
    - Chunks start at positions: 0, step, 2*step, ... where step = chunk_size - overlap
    - Each chunk is text[start:start+chunk_size]
    """
    if not text.strip():
        return []

    step = chunk_size - overlap
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text_str = text[start:end].strip()
        if chunk_text_str:
            chunks.append(KnowledgeChunk(
                content=chunk_text_str,
                source_page=source_page,
                chapter=chapter,
                source=SOURCE_NAME,
            ))
        start += step

    return chunks
