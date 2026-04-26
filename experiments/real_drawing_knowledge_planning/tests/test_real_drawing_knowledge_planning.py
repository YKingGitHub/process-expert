from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.agent_query_eval.src.query_api import KnowledgeQuery
from experiments.real_drawing_knowledge_planning.src.evaluator import (
    compare_route_families,
    evaluate_drawing_analysis,
    summarize_package,
)
from experiments.real_drawing_knowledge_planning.src.loader import (
    load_drawing_analysis,
    load_equipment_blank,
    load_reference_route,
)
from experiments.real_drawing_knowledge_planning.src.package_builder import build_knowledge_package
from experiments.real_drawing_knowledge_planning.src.planner import (
    plan_knowledge_needs,
    route_family_hypothesis,
)
from experiments.real_drawing_knowledge_planning.src.schema import (
    validate_drawing_analysis,
    validate_reference_route,
)


def test_drawing_analysis_fixture_has_key_manufacturing_features():
    drawing = load_drawing_analysis()

    assert validate_drawing_analysis(drawing) == []
    text = str(drawing)
    assert "φ103" in text
    assert "30.5" in text
    assert "φ0.1" in text
    assert "GB/T1804" in text


def test_drawing_quality_gate_exposes_missing_d_shape_feature():
    quality = evaluate_drawing_analysis(load_drawing_analysis())

    assert quality["status"] == "needs_review"
    failed = {flag["feature"] for flag in quality["flags"]}
    assert "d_shaped_or_milled_inner_profile" in failed


def test_reference_route_fixture_captures_expected_operation_families():
    route = load_reference_route()

    assert validate_reference_route(route) == []
    assert [item["operation"] for item in route["operations"]] == [
        "领料",
        "车",
        "线切割",
        "车",
        "铣",
        "钳",
        "检验",
        "入库",
    ]


def test_planner_produces_knowledge_needs_not_process_card():
    needs = plan_knowledge_needs(load_drawing_analysis(), load_equipment_blank())

    assert len(needs) >= 8
    assert {need["expected_knowledge_type"] for need in needs} >= {"principle", "lookup", "case", "candidate"}
    assert all("question" in need for need in needs)


def test_knowledge_package_exposes_current_kb_gaps():
    seed = load_source_replaced_seed()
    package = build_knowledge_package(
        plan_knowledge_needs(load_drawing_analysis(), load_equipment_blank()),
        KnowledgeQuery(seed),
        seed,
    )

    assert package["gap_report"]["gap_count"] >= 1
    candidate_types = {gap["candidate_type"] for gap in package["gap_report"]["gaps"]}
    assert "inspection_records" in candidate_types
    assert "standard_clause_records" in candidate_types


def test_route_family_hypothesis_matches_reference_at_family_level():
    hypothesis = route_family_hypothesis(load_drawing_analysis(), load_equipment_blank())
    route_eval = compare_route_families(hypothesis, load_reference_route())

    assert route_eval["recall"] >= 0.75
    assert route_eval["precision"] >= 0.75
    assert route_eval["missing_from_hypothesis"] == []


def test_end_to_end_summary_is_not_final_process_card():
    seed = load_source_replaced_seed()
    needs = plan_knowledge_needs(load_drawing_analysis(), load_equipment_blank())
    package = build_knowledge_package(needs, KnowledgeQuery(seed), seed)
    route_eval = compare_route_families(
        route_family_hypothesis(load_drawing_analysis(), load_equipment_blank()),
        load_reference_route(),
    )
    summary = summarize_package(package, route_eval)

    assert summary["need_count"] == len(needs)
    assert summary["gap_count"] >= 1
    assert summary["route_family_recall"] >= 0.75
