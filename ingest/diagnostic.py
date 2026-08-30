"""Diagnostic script — samples pages and evaluates parse/classify/extract quality."""

import argparse
import json
import os
import random
import re
import sqlite3
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from ingest.llm_client import get_client
from ingest.page_classifier import rule_based_preclassify
from ingest.pdf_extractor import extract_pages
from ingest.schemas import PageMarkdown


def load_unresolved_pages(output_dir="output"):
    """Load failed page numbers from unresolved.jsonl files."""
    pages = set()
    unresolved_path = os.path.join(output_dir, "unresolved.jsonl")
    if not os.path.exists(unresolved_path):
        print("[diagnostic] unresolved.jsonl not found, skipping historical failures")
        return pages
    with open(unresolved_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                pages.add(record.get("page_num"))
            except (json.JSONDecodeError, KeyError):
                continue
    print(f"[diagnostic] Loaded {len(pages)} unresolved page numbers")
    return pages


def sample_pages(total_pages: int, unresolved_pages: set, n=50) -> list[int]:
    """Stratified sampling: include unresolved pages + random fill to reach n."""
    sampled = set()
    # Include up to 20 unresolved pages
    unresolved_list = sorted(unresolved_pages)
    if len(unresolved_list) > 20:
        sampled.update(random.sample(unresolved_list, 20))
    else:
        sampled.update(unresolved_list)
    # Fill remaining with evenly distributed pages
    remaining = n - len(sampled)
    if remaining > 0:
        all_pages = set(range(1, total_pages + 1))
        available = sorted(all_pages - sampled)
        step = max(1, len(available) // remaining)
        for i in range(0, len(available), step):
            if len(sampled) >= n:
                break
            sampled.add(available[i])
    return sorted(sampled)[:n]


def evaluate_markdown_quality(markdown: str) -> dict:
    """Evaluate markdown table quality for a single page."""
    lines = markdown.split('\n')
    table_lines = [l for l in lines if '|' in l and not re.match(r'^\s*\|[-:\s|]+\|\s*$', l)]
    separator_lines = [l for l in lines if re.match(r'^\s*\|[-:\s|]+\|\s*$', l)]

    if not table_lines:
        return {
            "has_table": False,
            "table_rows": 0,
            "consistent_columns": False,
            "merged_cell_artifacts": False,
        }

    # Check column consistency
    col_counts = []
    for line in table_lines:
        cols = len([c for c in line.split('|') if c.strip() != ''])
        col_counts.append(cols)

    consistent = len(set(col_counts)) <= 2  # allow header vs data difference

    # Check for merged cell artifacts (many empty cells, <br> tags)
    empty_cell_count = sum(1 for l in table_lines for c in l.split('|') if c.strip() == '')
    total_cells = sum(len(l.split('|')) for l in table_lines)
    merged_artifacts = (empty_cell_count / max(total_cells, 1)) > 0.3

    return {
        "has_table": True,
        "table_rows": len(table_lines),
        "separator_rows": len(separator_lines),
        "consistent_columns": consistent,
        "merged_cell_artifacts": merged_artifacts,
        "column_counts": list(set(col_counts)),
    }


def evaluate_classification(page: PageMarkdown) -> dict:
    """Evaluate rule-based classification for a page."""
    rule_result = rule_based_preclassify(page.markdown_text)

    # Infer expected type from page content heuristics
    md_lower = page.markdown_text.lower()
    inferred = None
    if any(kw in md_lower for kw in ['公差等级', '偏差', 'h7', 'h6', '极限偏差']):
        inferred = 'tolerance_fits'
    elif any(kw in md_lower for kw in ['粗糙度', 'ra', 'rz']):
        inferred = 'surface_standards'
    elif any(kw in md_lower for kw in ['型号', '功率', '主轴转速']):
        inferred = 'equipment_specs'
    elif any(kw in md_lower for kw in ['切削速度', '进给量', '背吃刀量']):
        inferred = 'cutting_params'

    return {
        "rule_result": rule_result,
        "inferred_type": inferred,
        "rule_matches_inferred": rule_result == inferred if (rule_result and inferred) else None,
    }


def evaluate_extraction(page: PageMarkdown, client) -> dict:
    """Test extraction on a cutting_params page. Returns extraction stats."""
    try:
        from ingest.param_extractor import extract_params
        raw_params = extract_params(page, client)

        from ingest.validator import validate_param
        valid = []
        invalid_reasons = []
        for raw in raw_params:
            ok, result = validate_param(raw)
            if ok:
                valid.append(result)
            else:
                invalid_reasons.append(str(result))

        return {
            "raw_count": len(raw_params),
            "valid_count": len(valid),
            "validation_rate": len(valid) / max(len(raw_params), 1),
            "invalid_reasons": invalid_reasons[:5],  # first 5
            "error": None,
        }
    except Exception as e:
        return {
            "raw_count": 0,
            "valid_count": 0,
            "validation_rate": 0,
            "error": str(e),
        }


def run_diagnostic(pdf_path: str, db_path: str = None, output_dir: str = "output",
                   dry_run: bool = False, pages_file: str = None):
    """Main diagnostic entry point."""
    os.makedirs(output_dir, exist_ok=True)

    # Load unresolved pages
    unresolved = load_unresolved_pages(output_dir)

    # Get total page count
    import fitz
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    print(f"[diagnostic] PDF has {total_pages} pages")

    # Sample pages
    if pages_file and os.path.exists(pages_file):
        with open(pages_file) as f:
            sample = [int(x.strip()) for x in f.read().split(',') if x.strip()]
    else:
        sample = sample_pages(total_pages, unresolved, n=50)

    print(f"[diagnostic] Sampled {len(sample)} pages: {sample[:10]}...")

    if dry_run:
        print(f"[diagnostic] DRY RUN — sampled pages: {sample}")
        return sample

    # Initialize LLM client
    client = get_client()

    # Extract sampled pages
    results = []
    for page_num in sample:
        print(f"[diagnostic] Processing page {page_num}...")
        try:
            page_list = extract_pages(pdf_path, page_range=(page_num, page_num))
            if not page_list:
                results.append({"page_num": page_num, "error": "extraction_failed"})
                continue
            page = page_list[0]
        except Exception as e:
            results.append({"page_num": page_num, "error": f"pdf_extract: {e}"})
            continue

        # 1. Markdown quality
        md_quality = evaluate_markdown_quality(page.markdown_text)

        # 2. Classification
        classification = evaluate_classification(page)

        # 3. Extraction (only for cutting_params-like pages with good markdown)
        extraction = None
        inferred = classification.get("inferred_type") or classification.get("rule_result")
        if inferred == "cutting_params" and md_quality.get("has_table"):
            extraction = evaluate_extraction(page, client)

        results.append({
            "page_num": page_num,
            "is_unresolved": page_num in unresolved,
            "markdown_quality": md_quality,
            "classification": classification,
            "extraction": extraction,
            "markdown_snippet": page.markdown_text[:300],
        })

    # Write results
    out_path = os.path.join(output_dir, "diagnostic_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[diagnostic] Results written to {out_path} ({len(results)} pages)")
    return results


def main():
    parser = argparse.ArgumentParser(description="Pipeline diagnostic tool")
    parser.add_argument("--pdf", required=True, help="Path to source PDF")
    parser.add_argument("--db", default=None, help="Path to SQLite database")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Only output sampled page numbers")
    parser.add_argument("--pages-file", default=None, help="File with comma-separated page numbers")
    args = parser.parse_args()

    run_diagnostic(
        pdf_path=args.pdf,
        db_path=args.db,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        pages_file=args.pages_file,
    )


if __name__ == "__main__":
    main()
