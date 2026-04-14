"""PDF extraction module — wraps pymupdf4llm for page-by-page Markdown extraction."""

from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF
import pymupdf4llm

from ingest.schemas import PageMarkdown


def extract_pages(pdf_path: str) -> list[PageMarkdown]:
    """逐页提取 PDF 为 Markdown。返回 List[PageMarkdown]。"""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # pymupdf4llm 按页提取，page_chunks=True 返回 list of dict
    pages_md = pymupdf4llm.to_markdown(str(path), page_chunks=True)

    result = []
    for chunk in pages_md:
        # metadata["page_number"] 是 1-based 页码
        page_num = chunk.get("metadata", {}).get("page_number", 0)
        result.append(PageMarkdown(
            page_num=page_num,
            markdown_text=chunk.get("text", ""),
        ))

    print(f"[pdf_extractor] Extracted {len(result)} pages from {path.name}")
    return result


def extract_pages_with_fitz(pdf_path: str) -> Iterator[tuple]:
    """逐页提取 PDF，同时 yield (page_num, markdown_text, fitz_page) 三元组。

    fitz_page 对象在 doc 关闭前有效；调用方应在 doc 关闭前（即 generator 耗尽前）使用。
    page_num 为 1-indexed。
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(path))
    try:
        total = len(doc)
        print(f"[pdf_extractor] Opened {path.name} ({total} pages) for fitz extraction")
        for page_idx in range(total):
            fitz_page = doc[page_idx]
            # pymupdf4llm single-page extraction (0-indexed pages list)
            md = pymupdf4llm.to_markdown(doc, pages=[page_idx])
            yield page_idx + 1, md, fitz_page  # page_num 1-indexed
    finally:
        doc.close()
