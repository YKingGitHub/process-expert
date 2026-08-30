"""
ingest package — PDF ingestion pipeline for process knowledge base.

Modules:
    cli             — Pipeline entry point (argparse)
    pdf_extractor   — pymupdf4llm PDF → PageMarkdown
    page_classifier — LLM-based page type classification
    param_extractor — Structured param extraction from param_table pages
    knowledge_extractor — Knowledge chunk extraction from knowledge_table pages
    text_chunker    — Deterministic chunking for plain_text pages
    validator       — Pydantic schema validation
    cross_validator — Cross-model validation for failed records
    db_writer       — SQLite write operations
    llm_client      — DashScope API client wrapper
    schemas         — Pydantic data models
"""
