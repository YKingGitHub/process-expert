"""
Pipeline entry point — orchestrates the full PDF ingestion pipeline.

Usage:
    python ingest/cli.py --pdf <path> --db <path> [--max-pages N] [--pages START-END]
"""

import argparse
import json
import os
import sys

# Ensure repo root is in path when running as `python ingest/cli.py`
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import fitz  # PyMuPDF

from ingest.cross_validator import cross_validate
from ingest.db_writer import _ensure_schema, write_chunks, write_params
from ingest.knowledge_extractor import extract_knowledge
from ingest.llm_client import get_client
from ingest.multimodal_fallback import VLMFallback
from ingest.page_classifier import classify_pages
from ingest.param_extractor import extract_params
from ingest.pdf_extractor import extract_pages
from ingest.quality_reporter import QualityReporter
from ingest.schemas import PageMarkdown
from ingest.text_chunker import chunk_text
from ingest.validator import validate_param

_PROGRESS_INTERVAL = 50  # Print progress every N pages
_FLUSH_INTERVAL = 10    # Write to DB every N pages (incremental flush)


def parse_pages_range(pages_arg: str) -> tuple:
    """Parse --pages START-END argument. Returns (start, end) 1-indexed inclusive."""
    if "-" not in pages_arg:
        raise argparse.ArgumentTypeError(
            f"--pages must be in format START-END (e.g. '1-10'), got: {pages_arg}"
        )
    parts = pages_arg.split("-", 1)
    try:
        start = int(parts[0])
        end = int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--pages must contain integers, got: {pages_arg}"
        )
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError(
            f"--pages range invalid: {pages_arg}"
        )
    return start, end


def main():
    parser = argparse.ArgumentParser(
        description="Process knowledge base PDF ingestion pipeline"
    )
    parser.add_argument("--pdf", required=True, help="Path to source PDF file")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Maximum number of pages to process (for testing)")
    parser.add_argument("--pages", type=str, default=None,
                        help="Page range to process, e.g. '1-10' (1-indexed, inclusive)")
    args = parser.parse_args()

    # 1. Environment variable validation (fail-fast)
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("ERROR: DASHSCOPE_API_KEY not set — abort", file=sys.stderr)
        sys.exit(1)

    # 1b. Ensure DB schema exists (safe no-op if tables already present)
    import sqlite3 as _sqlite3
    _conn = _sqlite3.connect(args.db)
    _ensure_schema(_conn)
    _conn.close()
    del _conn, _sqlite3

    client = get_client()

    # 2. Parse page range filter
    page_range = None
    if args.pages:
        page_range = parse_pages_range(args.pages)
        print(f"[pipeline] Page range filter: {page_range[0]}-{page_range[1]}")

    # 3. Extract pages — pass page_range to avoid loading the full PDF into memory
    print(f"\n[pipeline] Extracting pages from {args.pdf} ...")
    pages = extract_pages(args.pdf, page_range=page_range)

    # Apply --max-pages filter (page_range already applied inside extract_pages)
    if args.max_pages:
        pages = pages[:args.max_pages]
        print(f"[pipeline] Limited to {args.max_pages} pages for testing")
    elif page_range:
        print(f"[pipeline] Extracted {len(pages)} pages for range {page_range[0]}-{page_range[1]}")

    total_pages = len(pages)

    # 4. Classify pages (batch, 10 pages per LLM call)
    print(f"\n[pipeline] Classifying {total_pages} pages ...")
    pages = classify_pages(pages, client)

    type_counts = {"param_table": 0, "knowledge_table": 0, "plain_text": 0, "unknown": 0}
    for p in pages:
        type_counts[p.page_type] = type_counts.get(p.page_type, 0) + 1
    print(f"[pipeline] Classification: {type_counts}")

    # 5. Open fitz document for VLM fallback (lazy rendering — only called on Tier 3)
    fitz_doc = fitz.open(args.pdf)
    vlm = VLMFallback(client)

    # 6. Prepare output directory and unresolved writer
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    unresolved_path = os.path.join(output_dir, "unresolved.jsonl")

    # 7. Stats counters
    stats = {
        "total_pages": total_pages,
        "tier1_success": 0,
        "tier2_success": 0,
        "tier3_success": 0,
        "unresolved": 0,
        "skipped_plain_text": 0,
    }

    all_params = []
    all_chunks = []

    # 8. Main extraction loop — Tier 1 → Tier 2 → Tier 3 → unresolved
    print(f"\n[pipeline] Processing {total_pages} pages (Tier1/2/3 fallback) ...")

    with open(unresolved_path, "a", encoding="utf-8") as f_unresolved:
        for idx, page in enumerate(pages):
            # Incremental flush every _FLUSH_INTERVAL pages so partial results survive timeouts
            if idx > 0 and idx % _FLUSH_INTERVAL == 0 and (all_params or all_chunks):
                pi, ps = write_params(args.db, all_params)
                ci, cs = write_chunks(args.db, all_chunks)
                print(f"[pipeline] Flush @page {idx}: params+={pi} chunks+={ci}", flush=True)
                all_params.clear()
                all_chunks.clear()
            # Progress reporting
            if (idx + 1) % _PROGRESS_INTERVAL == 0 or (idx + 1) == total_pages:
                print(
                    f"[pipeline] Progress: {idx + 1}/{total_pages} pages | "
                    f"t1={stats['tier1_success']} t2={stats['tier2_success']} "
                    f"t3={stats['tier3_success']} unresolved={stats['unresolved']} "
                    f"skipped={stats['skipped_plain_text']}"
                )

            if page.page_type == "plain_text":
                chunks = chunk_text(page.markdown_text, page.page_num)
                all_chunks.extend(chunks)
                stats["skipped_plain_text"] += 1
                continue

            if page.page_type == "knowledge_table":
                chunks = extract_knowledge(page, client)
                all_chunks.extend(chunks)
                # knowledge_table pages are processed as chunks; VLM only handles param extraction
                # If a knowledge_table page might also have params, it falls through to param path
                # For now: treat as processed (skipped for param tier tracking)
                stats["skipped_plain_text"] += 1
                continue

            # param_table pages — three-tier extraction
            raw_params = extract_params(page, client)

            # Tier 1: validate extracted params
            tier1_ok = []
            tier1_fail = []
            for raw in raw_params:
                ok, result = validate_param(raw)
                if ok:
                    tier1_ok.append(result)
                else:
                    tier1_fail.append((raw, result))

            if tier1_ok:
                all_params.extend(tier1_ok)
                stats["tier1_success"] += 1
                continue

            # Tier 2: cross-validate if Tier 1 produced no valid params
            if raw_params:
                cv_ok_params = []
                for raw, _ in tier1_fail:
                    cv_ok, cv_result = cross_validate(page, raw, client)
                    if cv_ok:
                        cv_ok_params.append(cv_result)

                if cv_ok_params:
                    all_params.extend(cv_ok_params)
                    stats["tier2_success"] += 1
                    continue

            # Tier 3: VLM multimodal fallback
            # fitz_page is 0-indexed; page.page_num is 1-indexed
            fitz_page = fitz_doc[page.page_num - 1]
            vlm_results = vlm.extract_with_vlm(fitz_page, page.page_num, page.page_type)

            if vlm_results:
                # Convert dicts back to ProcessParam objects for db_writer
                from ingest.validator import validate_param as vp
                validated_vlm = []
                for item in vlm_results:
                    ok, result = vp(item)
                    if ok:
                        validated_vlm.append(result)
                if validated_vlm:
                    all_params.extend(validated_vlm)
                    stats["tier3_success"] += 1
                    continue

            # Unresolved — all tiers failed
            record = {
                "page_num": page.page_num,
                "page_markdown_snippet": page.markdown_text[:500],
                "page_type": page.page_type,
                "fail_reason": "all_tiers_failed",
            }
            f_unresolved.write(json.dumps(record, ensure_ascii=False) + "\n")
            stats["unresolved"] += 1

    fitz_doc.close()

    # 9. Write to database
    print(f"\n[pipeline] Writing {len(all_params)} params and {len(all_chunks)} chunks to {args.db} ...")
    params_inserted, params_skipped = write_params(args.db, all_params)
    chunks_inserted, chunks_skipped = write_chunks(args.db, all_chunks)

    print(f"[pipeline] params: inserted={params_inserted} skipped={params_skipped}")
    print(f"[pipeline] chunks: inserted={chunks_inserted} skipped={chunks_skipped}")

    # 10. Quality report
    reporter = QualityReporter(output_dir=output_dir)
    reporter.report(stats, db_path=args.db)

    sys.exit(0)


if __name__ == "__main__":
    main()
