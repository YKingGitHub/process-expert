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

from ingest.db_writer import _ensure_schema, write_chunks, write_equipment, write_params, write_tolerance, write_surface
from ingest.knowledge_extractor import extract_knowledge
from ingest.llm_client import get_client
from ingest.multimodal_fallback import VLMFallback
from ingest.page_classifier import classify_pages
from ingest.param_extractor import extract_params
from ingest.pdf_extractor import extract_pages
from ingest.quality_reporter import QualityReporter
from ingest.schemas import PageMarkdown
from ingest.equipment_extractor import extract_equipment
from ingest.surface_extractor import extract_surface
from ingest.text_chunker import chunk_text
from ingest.tolerance_extractor import extract_tolerance
from ingest.validator import validate_param, validate_tolerance as vt_tolerance, validate_surface as vt_surface, validate_equipment as vt_equipment

_PROGRESS_INTERVAL = 50  # Print progress every N pages
_FLUSH_INTERVAL = 10    # Write to DB every N pages (incremental flush)

# Route dispatch table: page_type → handler name
PAGE_HANDLERS = {
    'cutting_params':    'extract_cutting',     # 2-tier: LLM + VLM
    'tolerance_fits':    'extract_tolerance',   # LLM + VLM
    'equipment_specs':   'extract_equipment',   # LLM + VLM
    'surface_standards': 'extract_surface',     # LLM + VLM
    'unit_conversion':   'fallback_to_chunks',  # 永久
    'knowledge_table':   'extract_knowledge',   # 现有
    'plain_text':        'chunk_text',           # 现有
}


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

    type_counts = {}
    for p in pages:
        type_counts[p.page_type] = type_counts.get(p.page_type, 0) + 1
    print(f"[pipeline] Classification: {type_counts}")

    # 5. Open fitz document for VLM fallback (lazy rendering — only called on Tier 3)
    fitz_doc = fitz.open(args.pdf)
    vlm = VLMFallback(client)

    # 6. Prepare output directory and unresolved writer
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    from datetime import datetime as _dt
    _unresolved_ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    unresolved_path = os.path.join(output_dir, f"unresolved_{_unresolved_ts}.jsonl")

    # 7. Stats counters
    stats = {
        "total_pages": total_pages,
        "tier1_success": 0,
        "tier3_success": 0,
        "unresolved": 0,
        "skipped_plain_text": 0,
        "tolerance_success": 0,
        "tolerance_vlm": 0,
        "surface_success": 0,
        "equipment_success": 0,
    }
    # Per-type page counts
    type_processed = {t: 0 for t in PAGE_HANDLERS}

    all_params = []
    all_chunks = []
    all_tolerance = []
    all_surface = []
    all_equipment = []
    filename = os.path.basename(args.pdf)

    def fallback_to_chunks(page, all_chunks_ref):
        """兜底路径：将页面内容走 chunk_text 存入 kb_chunks，标记 source 含 page_type。"""
        source_tag = f"fallback:{page.page_type}:p{page.page_num}"
        chunks = chunk_text(page.markdown_text, page.page_num)
        for c in chunks:
            c.source = source_tag
        all_chunks_ref.extend(chunks)

    # 8. Main extraction loop — route-based dispatch
    print(f"\n[pipeline] Processing {total_pages} pages (route-based dispatch) ...")

    with open(unresolved_path, "w", encoding="utf-8") as f_unresolved:
        for idx, page in enumerate(pages):
            # Incremental flush every _FLUSH_INTERVAL pages so partial results survive timeouts
            if idx > 0 and idx % _FLUSH_INTERVAL == 0 and (all_params or all_chunks or all_tolerance or all_surface or all_equipment):
                pi, _ = write_params(args.db, all_params) if all_params else (0, 0)
                ci, _ = write_chunks(args.db, all_chunks) if all_chunks else (0, 0)
                ti, _ = write_tolerance(args.db, all_tolerance) if all_tolerance else (0, 0)
                si, _ = write_surface(args.db, all_surface) if all_surface else (0, 0)
                ei, _ = write_equipment(args.db, all_equipment) if all_equipment else (0, 0)
                print(f"[pipeline] Flush @page {idx}: params+={pi} chunks+={ci} tol+={ti} surf+={si} equip+={ei}", flush=True)
                all_params.clear()
                all_chunks.clear()
                all_tolerance.clear()
                all_surface.clear()
                all_equipment.clear()
            # Progress reporting
            if (idx + 1) % _PROGRESS_INTERVAL == 0 or (idx + 1) == total_pages:
                print(
                    f"[pipeline] Progress: {idx + 1}/{total_pages} pages | "
                    f"t1={stats['tier1_success']} "
                    f"t3={stats['tier3_success']} unresolved={stats['unresolved']} "
                    f"skipped={stats['skipped_plain_text']}"
                )

            # Map legacy param_table to cutting_params
            page_type = page.page_type
            if page_type == "param_table":
                page_type = "cutting_params"

            handler = PAGE_HANDLERS.get(page_type, 'chunk_text')
            type_processed[page_type] = type_processed.get(page_type, 0) + 1

            if handler == 'chunk_text':
                chunks = chunk_text(page.markdown_text, page.page_num)
                all_chunks.extend(chunks)
                stats["skipped_plain_text"] += 1
                continue

            if handler == 'extract_knowledge':
                chunks = extract_knowledge(page, client)
                all_chunks.extend(chunks)
                stats["skipped_plain_text"] += 1
                continue

            if handler == 'fallback_to_chunks':
                fallback_to_chunks(page, all_chunks)
                stats["skipped_plain_text"] += 1
                continue

            # handler == 'extract_equipment' — equipment_specs pages (LLM only)
            if handler == 'extract_equipment':
                import sqlite3 as _sl3e
                _conn_e = _sl3e.connect(args.db)
                _existing_e = _conn_e.execute(
                    "SELECT COUNT(*) FROM equipment_specs WHERE source_page=?",
                    (page.page_num,)
                ).fetchone()[0]
                _conn_e.close()
                if _existing_e > 0:
                    stats["equipment_success"] += 1
                    continue

                raw_equip = extract_equipment(page, client)
                valid_equip = []
                for raw in raw_equip:
                    ok, result = vt_equipment(raw)
                    if ok:
                        valid_equip.append(result)

                # VLM fallback: trigger if empty or rows < 50% of expected
                md_lines = page.markdown_text.split('\n')
                expected_rows = sum(1 for line in md_lines
                                    if '|' in line and not line.strip().startswith('|--')
                                    and not line.strip().startswith('|-'))
                expected_rows = max(expected_rows - 1, 1)
                use_vlm = not valid_equip or (expected_rows > 0 and len(valid_equip) < expected_rows * 0.5)

                if valid_equip and not use_vlm:
                    all_equipment.extend(valid_equip)
                    stats["equipment_success"] += 1
                elif use_vlm:
                    fitz_page_e = fitz_doc[page.page_num - 1]
                    vlm_results = vlm.extract_equipment_vlm(fitz_page_e, page.page_num)
                    if vlm_results and len(vlm_results) > len(valid_equip):
                        all_equipment.extend(vlm_results)
                        stats["equipment_success"] += 1
                    elif valid_equip:
                        all_equipment.extend(valid_equip)
                        stats["equipment_success"] += 1
                    else:
                        record = {
                            "page_num": page.page_num,
                            "page_markdown_snippet": page.markdown_text[:500],
                            "page_type": page.page_type,
                            "fail_reason": "equipment_extraction_failed",
                        }
                        f_unresolved.write(json.dumps(record, ensure_ascii=False) + "\n")
                        stats["unresolved"] += 1
                continue

            # handler == 'extract_tolerance' — tolerance_fits pages (LLM + VLM)
            if handler == 'extract_tolerance':
                import sqlite3 as _sl3t
                _conn_t = _sl3t.connect(args.db)
                _existing_t = _conn_t.execute(
                    "SELECT COUNT(*) FROM tolerance_fits WHERE source_page=? "
                    "AND extraction_method IN ('llm_extracted','vlm_fallback')",
                    (page.page_num,)
                ).fetchone()[0]
                _conn_t.close()
                if _existing_t > 0:
                    stats["tolerance_success"] += 1
                    continue

                # Tier 1: LLM extraction
                raw_tol = extract_tolerance(page, client)
                tier1_valid = []
                for raw in raw_tol:
                    ok, result = vt_tolerance(raw)
                    if ok:
                        tier1_valid.append(result)

                # Estimate expected rows from markdown table lines
                md_lines = page.markdown_text.split('\n')
                expected_rows = sum(1 for line in md_lines
                                    if '|' in line and not line.strip().startswith('|--')
                                    and not line.strip().startswith('|-'))
                expected_rows = max(expected_rows - 1, 1)  # subtract header

                # Check if VLM fallback needed
                use_vlm = len(tier1_valid) == 0 or (expected_rows > 2 and len(tier1_valid) < expected_rows * 0.5)
                vlm_valid = []
                if use_vlm:
                    fitz_page_t = fitz_doc[page.page_num - 1]
                    vlm_raw = vlm.extract_tolerance_vlm(fitz_page_t, page.page_num)
                    for raw in vlm_raw:
                        ok, result = vt_tolerance(raw)
                        if ok:
                            vlm_valid.append(result)

                # Take the set with more valid rows
                if vlm_valid and len(vlm_valid) > len(tier1_valid):
                    final = vlm_valid
                    stats["tolerance_vlm"] += 1
                else:
                    final = tier1_valid

                if final:
                    all_tolerance.extend(final)
                    stats["tolerance_success"] += 1
                else:
                    record = {
                        "page_num": page.page_num,
                        "page_markdown_snippet": page.markdown_text[:500],
                        "page_type": page.page_type,
                        "fail_reason": "tolerance_all_tiers_failed",
                    }
                    f_unresolved.write(json.dumps(record, ensure_ascii=False) + "\n")
                    stats["unresolved"] += 1
                continue

            # handler == 'extract_surface' — surface_standards pages (LLM only)
            if handler == 'extract_surface':
                import sqlite3 as _sl3s
                _conn_s = _sl3s.connect(args.db)
                _existing_s = _conn_s.execute(
                    "SELECT COUNT(*) FROM surface_standards WHERE source_page=? "
                    "AND extraction_method IN ('llm_extracted','vlm_fallback')",
                    (page.page_num,)
                ).fetchone()[0]
                _conn_s.close()
                if _existing_s > 0:
                    stats["surface_success"] += 1
                    continue

                raw_surf = extract_surface(page, client)
                valid_surf = []
                for raw in raw_surf:
                    ok, result = vt_surface(raw)
                    if ok:
                        valid_surf.append(result)

                # VLM fallback: trigger if empty or rows < 50% of expected
                md_lines_s = page.markdown_text.split('\n')
                expected_rows_s = sum(1 for line in md_lines_s
                                      if '|' in line and not line.strip().startswith('|--')
                                      and not line.strip().startswith('|-'))
                expected_rows_s = max(expected_rows_s - 1, 1)
                use_vlm_s = not valid_surf or (expected_rows_s > 0 and len(valid_surf) < expected_rows_s * 0.5)

                if valid_surf and not use_vlm_s:
                    all_surface.extend(valid_surf)
                    stats["surface_success"] += 1
                elif use_vlm_s:
                    fitz_page_s = fitz_doc[page.page_num - 1]
                    vlm_results_s = vlm.extract_surface_vlm(fitz_page_s, page.page_num)
                    if vlm_results_s and len(vlm_results_s) > len(valid_surf):
                        all_surface.extend(vlm_results_s)
                        stats["surface_success"] += 1
                    elif valid_surf:
                        all_surface.extend(valid_surf)
                        stats["surface_success"] += 1
                    else:
                        record = {
                            "page_num": page.page_num,
                            "page_markdown_snippet": page.markdown_text[:500],
                            "page_type": page.page_type,
                            "fail_reason": "surface_extraction_failed",
                        }
                        f_unresolved.write(json.dumps(record, ensure_ascii=False) + "\n")
                        stats["unresolved"] += 1
                continue

            # handler == 'extract_cutting' — cutting_params pages
            # Skip if already processed (idempotent re-run / resume)
            import sqlite3 as _sl3
            _conn_check = _sl3.connect(args.db)
            _existing = _conn_check.execute(
                "SELECT COUNT(*) FROM cutting_params WHERE source_page=? "
                "AND extraction_method IN ('llm_extracted','vlm_fallback')",
                (page.page_num,)
            ).fetchone()[0]
            _conn_check.close()
            if _existing > 0:
                stats["tier1_success"] += 1
                continue

            # Three-tier extraction
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

            # Tier 2: VLM multimodal fallback
            fitz_page = fitz_doc[page.page_num - 1]
            vlm_results = vlm.extract_with_vlm(fitz_page, page.page_num, page.page_type)

            if vlm_results:
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
    print(f"\n[pipeline] Writing {len(all_params)} params, {len(all_chunks)} chunks, "
          f"{len(all_tolerance)} tolerance, {len(all_surface)} surface, "
          f"{len(all_equipment)} equipment to {args.db} ...")
    params_inserted, _ = write_params(args.db, all_params) if all_params else (0, 0)
    chunks_inserted, _ = write_chunks(args.db, all_chunks) if all_chunks else (0, 0)
    tol_inserted, _ = write_tolerance(args.db, all_tolerance) if all_tolerance else (0, 0)
    surf_inserted, _ = write_surface(args.db, all_surface) if all_surface else (0, 0)
    equip_inserted, _ = write_equipment(args.db, all_equipment) if all_equipment else (0, 0)

    print(f"[pipeline] params: inserted={params_inserted}")
    print(f"[pipeline] chunks: inserted={chunks_inserted}")
    print(f"[pipeline] tolerance: inserted={tol_inserted}")
    print(f"[pipeline] surface: inserted={surf_inserted}")
    print(f"[pipeline] equipment: inserted={equip_inserted}")
    print(f"[pipeline] Per-type page counts: {type_processed}")

    # 10. Quality report
    reporter = QualityReporter(output_dir=output_dir)
    reporter.report(stats, db_path=args.db)

    sys.exit(0)


if __name__ == "__main__":
    main()
