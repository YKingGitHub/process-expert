#!/usr/bin/env python3
"""Run Agent knowledge query evaluation."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.agent_query_eval.src.data_loader import (  # noqa: E402
    load_seed,
    load_questions,
)
from experiments.agent_query_eval.src.evaluator import evaluate_questions  # noqa: E402
from experiments.agent_query_eval.src.query_api import KnowledgeQuery  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


def main() -> int:
    parser = ArgumentParser(description="Run Agent knowledge query evaluation.")
    parser.add_argument(
        "--seed",
        choices=("source", "gold"),
        default="source",
        help="Seed dataset to evaluate. Defaults to source-replaced Sprint B seed.",
    )
    args = parser.parse_args()

    questions = load_questions()
    seed = load_seed(args.seed)
    query = KnowledgeQuery(seed)
    report = evaluate_questions(questions, query)
    report_path = OUTPUT_DIR / f"agent_query_eval_report_{args.seed}.json"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary(report, args.seed, report_path), ensure_ascii=False, indent=2))
    return 0 if report["intent_accuracy"] >= 0.9 and report["pass_rate"] >= 0.9 else 1


def summary(report: dict, seed_name: str, report_path: Path) -> dict:
    failed = [item["id"] for item in report["results"] if not item["passed"]]
    return {
        "question_count": report["question_count"],
        "passed_count": report["passed_count"],
        "pass_rate": report["pass_rate"],
        "intent_accuracy": report["intent_accuracy"],
        "failed": failed,
        "seed": seed_name,
        "report_path": str(report_path),
    }


if __name__ == "__main__":
    raise SystemExit(main())
