#!/usr/bin/env python3
"""Run Agent knowledge query evaluation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.agent_query_eval.src.data_loader import (  # noqa: E402
    load_gold_seed,
    load_questions,
)
from experiments.agent_query_eval.src.evaluator import evaluate_questions  # noqa: E402
from experiments.agent_query_eval.src.query_api import KnowledgeQuery  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
REPORT_PATH = OUTPUT_DIR / "agent_query_eval_report.json"


def main() -> int:
    questions = load_questions()
    seed = load_gold_seed()
    query = KnowledgeQuery(seed)
    report = evaluate_questions(questions, query)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0 if report["intent_accuracy"] >= 0.9 and report["pass_rate"] >= 0.9 else 1


def summary(report: dict) -> dict:
    failed = [item["id"] for item in report["results"] if not item["passed"]]
    return {
        "question_count": report["question_count"],
        "passed_count": report["passed_count"],
        "pass_rate": report["pass_rate"],
        "intent_accuracy": report["intent_accuracy"],
        "failed": failed,
        "report_path": str(REPORT_PATH),
    }


if __name__ == "__main__":
    raise SystemExit(main())
