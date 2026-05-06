"""Run B1 capability seed expansion evaluation.

Usage:
    python3 experiments/capability_seed_expansion/scripts/evaluate.py

Prints a JSON summary to stdout and writes the full report to
``experiments/capability_seed_expansion/output/evaluate_report.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed  # noqa: E402
from experiments.agent_query_eval.src.query_api import KnowledgeQuery  # noqa: E402
from experiments.capability_seed_expansion.src.expanded_evaluator import (  # noqa: E402
    candidate_records_by_family,
    compare_baseline_vs_expanded,
    evaluate_baseline,
    evaluate_expanded,
    records_blocked_by_quality_status,
)
from experiments.capability_seed_expansion.src.expanded_query import (  # noqa: E402
    ExpandedKnowledgeQuery,
)
from experiments.capability_seed_expansion.src.loader import (  # noqa: E402
    load_candidate_seed,
    load_source_manifest,
    validate_candidate_seed,
    validate_source_manifest,
)
from experiments.capability_seed_expansion.src.seed_merge import build_expanded_seed  # noqa: E402
from experiments.knowledge_capability_eval.src.loader import (  # noqa: E402
    load_capability_questions,
    load_real_drawing_gap_map,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = EXPERIMENT_ROOT / "output"
OUTPUT_PATH = OUTPUT_DIR / "evaluate_report.json"


def run() -> dict:
    base_seed = load_source_replaced_seed()
    candidate_seed = load_candidate_seed()
    manifest = load_source_manifest()
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()

    seed_errors = validate_candidate_seed(candidate_seed)
    manifest_errors = validate_source_manifest(manifest, candidate_seed)
    if seed_errors or manifest_errors:
        return {
            "status": "fixture_invalid",
            "seed_errors": seed_errors,
            "manifest_errors": manifest_errors,
        }

    expanded_seed = build_expanded_seed(base_seed, candidate_seed)

    baseline_report = evaluate_baseline(
        questions, KnowledgeQuery(base_seed), gap_map
    )
    expanded_report = evaluate_expanded(
        questions, ExpandedKnowledgeQuery(expanded_seed), gap_map
    )
    delta = compare_baseline_vs_expanded(baseline_report, expanded_report)

    full_report = {
        "status": delta["status"],
        "baseline_gap_count": delta.get("baseline_gap_count"),
        "expanded_gap_count": delta.get("expanded_gap_count"),
        "gap_reduction": delta.get("gap_reduction"),
        "gap_delta_by_capability": delta.get("gap_delta_by_capability"),
        "real_drawing_mapped_gap_covered_count": delta.get(
            "real_drawing_mapped_gap_covered_count"
        ),
        "real_drawing_mapped_gap_total": delta.get(
            "real_drawing_mapped_gap_total"
        ),
        "candidate_records_by_family": candidate_records_by_family(candidate_seed),
        "records_blocked_by_quality_status": records_blocked_by_quality_status(
            candidate_seed
        ),
        "baseline_gap_count_by_capability": baseline_report.get(
            "gap_count_by_capability"
        ),
        "expanded_gap_count_by_capability": expanded_report.get(
            "gap_count_by_capability"
        ),
        "transitions": delta.get("transitions", []),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(full_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return full_report


def main() -> None:
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
