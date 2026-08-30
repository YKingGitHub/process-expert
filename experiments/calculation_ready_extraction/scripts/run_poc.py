#!/usr/bin/env python3
"""Run the calculation-ready extraction POC end to end."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.calculation_ready_extraction.src.calculation import (  # noqa: E402
    calculate_cylinder_liner_allowance,
)
from experiments.calculation_ready_extraction.src.db_builder import build_db  # noqa: E402
from experiments.calculation_ready_extraction.src.loader import (  # noqa: E402
    load_p108_gold,
    load_vlm_pages,
)
from experiments.calculation_ready_extraction.src.quality_gate import (  # noqa: E402
    evaluate_pages,
)
from experiments.calculation_ready_extraction.src.route_merge import merge_routes  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = EXPERIMENT_ROOT / "output"
DB_PATH = OUTPUT_DIR / "calculation_ready_poc.db"
REPORT_PATH = OUTPUT_DIR / "calculation_ready_report.json"


def main() -> int:
    pages = load_vlm_pages()
    gold = load_p108_gold()
    quality = evaluate_pages(pages, gold_payloads=[gold])
    routes = merge_routes(pages)
    build_db(routes, DB_PATH, quality_flags=quality["flags"])

    cylinder_route = next(route for route in routes if route.part_name == "缸套")
    allowance_result = calculate_cylinder_liner_allowance(cylinder_route)

    report = {
        "quality": quality,
        "routes": [
            {
                "route_id": route.route_id,
                "part_name": route.part_name,
                "table_ref": route.table_ref,
                "source_pages": route.source_pages,
                "step_numbers": route.step_numbers,
                "step_count": len(route.steps),
                "flags": route.flags,
            }
            for route in routes
        ],
        "calculation": {
            "cylinder_liner_allowance": allowance_result,
        },
        "db": {
            "path": str(DB_PATH),
            "counts": db_counts(DB_PATH),
        },
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0


def db_counts(db_path: Path) -> dict:
    with sqlite3.connect(db_path) as conn:
        return {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "process_routes",
                "process_steps",
                "process_dimensions",
                "process_allowances",
            )
        }


def summary(report: dict) -> dict:
    return {
        "quality_status": report["quality"]["status"],
        "quality_flag_count": report["quality"]["flag_count"],
        "routes": {
            route["part_name"]: route["step_count"] for route in report["routes"]
        },
        "db_counts": report["db"]["counts"],
        "cylinder_inner_allowance": report["calculation"]["cylinder_liner_allowance"]["result"][
            "inner_finish_to_grind_allowance"
        ],
        "cylinder_outer_allowance": report["calculation"]["cylinder_liner_allowance"]["result"][
            "outer_finish_to_grind_allowance"
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
