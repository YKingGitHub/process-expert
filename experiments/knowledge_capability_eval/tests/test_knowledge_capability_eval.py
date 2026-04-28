from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.agent_query_eval.src.query_api import KnowledgeQuery
from experiments.knowledge_capability_eval.src.evaluator import (
    evaluate_capabilities,
    validate_question_set,
    validate_real_drawing_gap_map,
)
from experiments.knowledge_capability_eval.src.loader import (
    load_capability_questions,
    load_real_drawing_gap_map,
)


def make_report() -> dict:
    return evaluate_capabilities(
        load_capability_questions(),
        KnowledgeQuery(load_source_replaced_seed()),
        load_real_drawing_gap_map(),
    )


def test_question_set_meets_capability_acceptance_criteria():
    questions = load_capability_questions()

    assert validate_question_set(questions) == []
    capabilities = {item["capability"] for item in questions}
    assert len(capabilities) >= 7
    for capability in capabilities:
        assert sum(1 for item in questions if item["capability"] == capability) >= 3
    assert all(item["expected_family"] for item in questions)
    assert all(item["expected_subtype"] for item in questions)
    assert all(item["expected_contract"] for item in questions)


def test_real_drawing_gaps_map_to_capabilities():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()

    assert validate_real_drawing_gap_map(gap_map, questions) == []
    mapped_candidate_types = {item["candidate_type"] for item in gap_map}
    assert "inspection_records" in mapped_candidate_types
    assert "standard_clause_records" in mapped_candidate_types
    assert "machining_allowance_records" in mapped_candidate_types
    assert "equipment_capability_records" in mapped_candidate_types
    assert "milling_process_records" in mapped_candidate_types


def test_capability_report_exposes_gap_counts_by_capability():
    report = make_report()

    assert report["status"] == "valid"
    assert report["question_count"] >= 21
    assert report["capability_count"] >= 7
    assert report["gap_count"] >= 1
    assert set(report["gap_count_by_capability"]) >= {
        "drawing_requirement_interpretation",
        "geometric_tolerance_inspection",
        "equipment_operation_capability",
        "feature_process_selection",
        "machining_allowance_planning",
        "route_planning",
        "deterministic_calculation",
    }


def test_current_seed_has_both_supported_capabilities_and_real_gaps():
    report = make_report()

    assert report["covered_count"] >= 5
    assert report["capability_summary"]["route_planning"]["covered_count"] >= 2
    assert report["capability_summary"]["machining_allowance_planning"]["covered_count"] >= 2
    assert report["capability_summary"]["drawing_requirement_interpretation"]["gap_count"] >= 3
    assert report["capability_summary"]["feature_process_selection"]["gap_count"] >= 2


def test_real_drawing_gap_capabilities_are_visible_in_report():
    report = make_report()

    real_gap_counts = report["real_drawing_gap_count_by_capability"]
    assert real_gap_counts["drawing_requirement_interpretation"] >= 2
    assert real_gap_counts["feature_process_selection"] >= 2
    assert real_gap_counts["geometric_tolerance_inspection"] >= 1
    assert real_gap_counts["machining_allowance_planning"] >= 1
    assert real_gap_counts["equipment_operation_capability"] >= 1

