#!/usr/bin/env python3
"""Evaluate the real drawing knowledge planning POC."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed  # noqa: E402
from experiments.agent_query_eval.src.query_api import KnowledgeQuery  # noqa: E402
from experiments.real_drawing_knowledge_planning.src.evaluator import (  # noqa: E402
    compare_route_families,
    evaluate_drawing_analysis,
    summarize_package,
)
from experiments.real_drawing_knowledge_planning.src.loader import (  # noqa: E402
    load_cad_summary,
    load_drawing_analysis,
    load_equipment_blank,
    load_reference_route,
)
from experiments.real_drawing_knowledge_planning.src.package_builder import (  # noqa: E402
    build_knowledge_package,
)
from experiments.real_drawing_knowledge_planning.src.planner import (  # noqa: E402
    plan_knowledge_needs,
    route_family_hypothesis,
)
from experiments.real_drawing_knowledge_planning.src.schema import (  # noqa: E402
    validate_drawing_analysis,
    validate_reference_route,
)


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
REPORT_PATH = OUTPUT_DIR / "real_drawing_knowledge_planning_report.json"


def main() -> int:
    drawing = load_drawing_analysis()
    constraints = load_equipment_blank()
    cad_summary = load_cad_summary()
    reference_route = load_reference_route()

    drawing_errors = validate_drawing_analysis(drawing)
    route_errors = validate_reference_route(reference_route)
    if drawing_errors or route_errors:
        raise SystemExit(json.dumps({"drawing_errors": drawing_errors, "route_errors": route_errors}, ensure_ascii=False, indent=2))

    seed = load_source_replaced_seed()
    needs = plan_knowledge_needs(drawing, constraints)
    query = KnowledgeQuery(seed)
    package = build_knowledge_package(needs, query, seed)
    route_eval = compare_route_families(route_family_hypothesis(drawing, constraints), reference_route)
    drawing_quality = evaluate_drawing_analysis(drawing)
    summary = summarize_package(package, route_eval)

    report = {
        "summary": summary,
        "drawing_quality": drawing_quality,
        "drawing_analysis": drawing,
        "equipment_blank": constraints,
        "cad_summary": cad_summary,
        "knowledge_needs": needs,
        "knowledge_package": package,
        "route_family_eval": route_eval,
        "non_goals": ["This report is not a final process card."],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report_path": str(REPORT_PATH), "drawing_quality": drawing_quality["status"], **summary}, ensure_ascii=False, indent=2))
    return 0 if summary["route_family_recall"] >= 0.75 and summary["gap_count"] >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
