#!/usr/bin/env python3
"""Export frozen fixtures for the extracted-content calculation POC."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


DEFAULT_DB = Path("/root/process-expert/output/unified_extract.db")
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = EXPERIMENT_ROOT / "fixtures"


def fetch_rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql)]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}")

    with sqlite3.connect(args.db) as conn:
        process_cards = fetch_rows(
            conn,
            """
            select
              id, page_num, toc_path, part_name, table_ref, step_no,
              operation_name, operation_content, equipment
            from process_card_records
            order by page_num, table_ref, step_no, id
            """,
        )
        computation_methods = fetch_rows(
            conn,
            """
            select
              id, page_num, toc_path, method_name, description, formula,
              inputs_json, outputs_json, example_json
            from computation_methods
            order by id
            """,
        )

    expected_cases = {
        "output_shaft": {
            "canonical_part_name": "输出轴",
            "source_part_names": ["输出轴", "轴类零件（续）"],
            "expected_step_count": 12,
            "expected_step_numbers": list(range(1, 13)),
            "expected_categories": [
                "blank_preparation",
                "treatment_or_auxiliary",
                "rough_or_general_machining",
                "finish_machining",
                "inspection",
                "storage",
            ],
        },
        "seal_positioning_sleeve": {
            "canonical_part_name": "密封件定位套",
            "source_part_names": ["密封件定位套"],
            "expected_step_count": 13,
            "expected_step_numbers": list(range(1, 14)),
            "expected_categories": [
                "blank_preparation",
                "treatment_or_auxiliary",
                "rough_or_general_machining",
                "finish_machining",
                "inspection",
                "storage",
            ],
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "process_cards_sample.json", process_cards)
    write_json(args.out / "computation_methods_sample.json", computation_methods)
    write_json(args.out / "expected_cases.json", expected_cases)

    print(f"exported process cards: {len(process_cards)}")
    print(f"exported computation methods: {len(computation_methods)}")
    print(f"fixture dir: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
