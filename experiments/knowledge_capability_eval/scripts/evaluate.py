#!/usr/bin/env python3
"""Run the knowledge capability baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed  # noqa: E402
from experiments.agent_query_eval.src.query_api import KnowledgeQuery  # noqa: E402
from experiments.knowledge_capability_eval.src.evaluator import evaluate_capabilities  # noqa: E402
from experiments.knowledge_capability_eval.src.loader import (  # noqa: E402
    load_capability_questions,
    load_real_drawing_gap_map,
)


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
REPORT_PATH = OUTPUT_DIR / "knowledge_capability_eval_report.json"


def main() -> int:
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    query = KnowledgeQuery(load_source_replaced_seed())
    report = evaluate_capabilities(questions, query, gap_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0 if report["status"] == "valid" else 1


def summary(report: dict) -> dict:
    return {
        "status": report["status"],
        "question_count": report.get("question_count"),
        "capability_count": report.get("capability_count"),
        "covered_count": report.get("covered_count"),
        "gap_count": report.get("gap_count"),
        "gap_count_by_capability": report.get("gap_count_by_capability"),
        "real_drawing_gap_count_by_capability": report.get("real_drawing_gap_count_by_capability"),
        "report_path": str(REPORT_PATH),
    }


if __name__ == "__main__":
    raise SystemExit(main())

