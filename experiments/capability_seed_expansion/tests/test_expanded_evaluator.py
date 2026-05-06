"""Tests for B1 expanded evaluator and the WO-B1-003 acceptance gates."""

from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.agent_query_eval.src.query_api import KnowledgeQuery
from experiments.capability_seed_expansion.scripts.evaluate import run as run_evaluate
from experiments.capability_seed_expansion.src.expanded_evaluator import (
    EXPANDED_CORE_FAMILIES,
    EXPANDED_KNOWLEDGE_TYPE_TO_FAMILY,
    candidate_records_by_family,
    compare_baseline_vs_expanded,
    evaluate_baseline,
    evaluate_expanded,
    records_blocked_by_quality_status,
)
from experiments.capability_seed_expansion.src.expanded_query import (
    ExpandedKnowledgeQuery,
)
from experiments.capability_seed_expansion.src.loader import load_candidate_seed
from experiments.capability_seed_expansion.src.seed_merge import build_expanded_seed
from experiments.knowledge_capability_eval.src.loader import (
    load_capability_questions,
    load_real_drawing_gap_map,
)


B1_FAMILIES = {
    "standard_clause_records",
    "inspection_records",
    "equipment_capability_records",
}


def test_expanded_core_families_include_all_three_b1_families():
    for family in B1_FAMILIES:
        assert family in EXPANDED_CORE_FAMILIES


def test_expanded_knowledge_type_to_family_covers_b1_types():
    for kt in ("standard_clause", "inspection", "equipment_capability"):
        assert kt in EXPANDED_KNOWLEDGE_TYPE_TO_FAMILY


def test_baseline_evaluator_matches_sprint_a_baseline():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    report = evaluate_baseline(
        questions, KnowledgeQuery(load_source_replaced_seed()), gap_map
    )
    assert report["status"] == "valid"
    assert report["question_count"] == 21
    assert report["capability_count"] == 7
    assert report["covered_count"] == 10
    assert report["gap_count"] == 11


def test_expanded_evaluator_meets_gap_acceptance_gate():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    base_seed = load_source_replaced_seed()
    candidate_seed = load_candidate_seed()
    expanded_seed = build_expanded_seed(base_seed, candidate_seed)

    report = evaluate_expanded(
        questions, ExpandedKnowledgeQuery(expanded_seed), gap_map
    )
    assert report["status"] == "valid"
    assert report["question_count"] == 21
    assert report["gap_count"] <= 8, (
        f"WO-B1-003 acceptance: expanded_gap_count must be <= 8, got "
        f"{report['gap_count']}"
    )


def test_real_drawing_mapped_gap_recovery_meets_gate():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    base_seed = load_source_replaced_seed()
    candidate_seed = load_candidate_seed()
    expanded_seed = build_expanded_seed(base_seed, candidate_seed)

    baseline = evaluate_baseline(questions, KnowledgeQuery(base_seed), gap_map)
    expanded = evaluate_expanded(
        questions, ExpandedKnowledgeQuery(expanded_seed), gap_map
    )
    delta = compare_baseline_vs_expanded(baseline, expanded)

    assert delta["status"] == "valid"
    assert delta["real_drawing_mapped_gap_covered_count"] >= 2, (
        f"WO-B1-003 acceptance: real_drawing_mapped_gap_covered_count must be "
        f">= 2, got {delta['real_drawing_mapped_gap_covered_count']}"
    )


def test_no_baseline_covered_question_regresses():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    base_seed = load_source_replaced_seed()
    candidate_seed = load_candidate_seed()
    expanded_seed = build_expanded_seed(base_seed, candidate_seed)

    baseline = evaluate_baseline(questions, KnowledgeQuery(base_seed), gap_map)
    expanded = evaluate_expanded(
        questions, ExpandedKnowledgeQuery(expanded_seed), gap_map
    )
    delta = compare_baseline_vs_expanded(baseline, expanded)

    regressions = [
        t for t in delta["transitions"] if t["transition"] == "covered_to_uncovered"
    ]
    assert regressions == [], (
        f"B1 must not regress baseline-covered questions: {regressions}"
    )


def test_evaluate_script_writes_report_with_required_fields():
    report = run_evaluate()
    required = {
        "baseline_gap_count",
        "expanded_gap_count",
        "gap_reduction",
        "gap_delta_by_capability",
        "real_drawing_mapped_gap_covered_count",
        "real_drawing_mapped_gap_total",
        "candidate_records_by_family",
        "records_blocked_by_quality_status",
    }
    for field in required:
        assert field in report, f"report missing {field}"


def test_candidate_records_by_family_counts_all_three_families():
    candidate = load_candidate_seed()
    counts = candidate_records_by_family(candidate)
    for family in B1_FAMILIES:
        assert counts.get(family, 0) >= 1


def test_no_b1_record_currently_blocked_by_needs_human_review():
    """B1 design says needs_human_review records cannot count as covered.
    Current B1 seed should not rely on any such record for gap reduction."""
    candidate = load_candidate_seed()
    blocked = records_blocked_by_quality_status(candidate)
    for family, count in blocked.items():
        assert count == 0, (
            f"family {family} has {count} needs_human_review records"
        )
