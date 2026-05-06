"""B2 evaluator tests + WO-B2-003 acceptance gate verification."""

from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.agent_query_eval.src.query_api import KnowledgeQuery
from experiments.capability_seed_expansion.scripts.evaluate import run as run_evaluate
from experiments.capability_seed_expansion.src.expanded_evaluator import (
    EXPANDED_CORE_FAMILIES,
    EXPANDED_KNOWLEDGE_TYPE_TO_FAMILY,
    compare_baseline_vs_expanded,
    evaluate_baseline,
    evaluate_expanded,
)
from experiments.capability_seed_expansion.src.expanded_query import (
    B2_CANDIDATE_FAMILIES,
    ExpandedKnowledgeQuery,
)
from experiments.capability_seed_expansion.src.loader import load_candidate_seed
from experiments.capability_seed_expansion.src.seed_merge import build_expanded_seed
from experiments.knowledge_capability_eval.src.loader import (
    load_capability_questions,
    load_real_drawing_gap_map,
)


def make_reports():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    base_seed = load_source_replaced_seed()
    candidate = load_candidate_seed()
    expanded_seed = build_expanded_seed(base_seed, candidate)
    baseline = evaluate_baseline(questions, KnowledgeQuery(base_seed), gap_map)
    expanded = evaluate_expanded(
        questions, ExpandedKnowledgeQuery(expanded_seed), gap_map
    )
    delta = compare_baseline_vs_expanded(baseline, expanded)
    return baseline, expanded, delta


def test_expanded_core_families_contain_all_b2_families():
    for family in B2_CANDIDATE_FAMILIES:
        assert family in EXPANDED_CORE_FAMILIES


def test_expanded_knowledge_type_to_family_includes_b2_types():
    for kt in (
        "drawing_requirement",
        "machining_allowance",
        "feature_process",
        "milling_process",
    ):
        assert kt in EXPANDED_KNOWLEDGE_TYPE_TO_FAMILY


def test_baseline_unchanged_after_b2():
    """Sprint A baseline must report 11/21 regardless of B2 work."""
    baseline, _, _ = make_reports()
    assert baseline["question_count"] == 21
    assert baseline["covered_count"] == 10
    assert baseline["gap_count"] == 11


def test_b2_meets_expanded_gap_acceptance_gate():
    """WO-B2-003 acceptance: expanded_gap_count <= 2."""
    _, expanded, _ = make_reports()
    assert expanded["gap_count"] <= 2, (
        f"WO-B2-003 acceptance: expanded_gap_count must be <= 2, got "
        f"{expanded['gap_count']}"
    )


def test_b2_meets_real_drawing_gap_recovery_gate():
    """WO-B2-003 acceptance: real_drawing_mapped_gap_covered_count >= 5."""
    _, _, delta = make_reports()
    assert delta["real_drawing_mapped_gap_covered_count"] >= 5, (
        f"WO-B2-003 acceptance: real_drawing_mapped_gap_covered_count must be "
        f">= 5, got {delta['real_drawing_mapped_gap_covered_count']}"
    )


def test_b2_b1_transitions_still_present():
    """B1's five transitions must persist after B2 (no regression)."""
    _, _, delta = make_reports()
    transition_ids = {
        t["id"] for t in delta["transitions"]
        if t["transition"] == "uncovered_to_covered"
    }
    for tid in ("DRI-001", "GTI-001", "GTI-003", "EOC-002", "EOC-003"):
        assert tid in transition_ids, (
            f"B1 transition {tid} regressed after B2 changes"
        )


def test_b2_target_question_transitions_succeed():
    """B2 target capability questions must all transition to covered."""
    _, _, delta = make_reports()
    transition_ids = {
        t["id"] for t in delta["transitions"]
        if t["transition"] == "uncovered_to_covered"
    }
    for tid in ("DRI-002", "DRI-003", "FPS-001", "FPS-002", "MAP-003"):
        assert tid in transition_ids, (
            f"B2 target {tid} did not transition to covered"
        )


def test_b2_no_regression_to_baseline_covered_questions():
    """No previously-covered question becomes uncovered."""
    _, _, delta = make_reports()
    regressions = [
        t for t in delta["transitions"] if t["transition"] == "covered_to_uncovered"
    ]
    assert regressions == [], (
        f"B2 must not regress baseline-covered questions: {regressions}"
    )


def test_b2_only_dca_003_remains_uncovered_in_expanded():
    """Only DCA-003 (deterministic_calculation) should remain uncovered;
    it requires Sprint C process_calc.calculate() implementation."""
    _, expanded, _ = make_reports()
    uncovered = [r for r in expanded["results"] if not r["covered"]]
    uncovered_ids = sorted(r["id"] for r in uncovered)
    # Allow up to 2 uncovered (per design); DCA-003 must be among them.
    assert "DCA-003" in uncovered_ids
    assert len(uncovered_ids) <= 2


def test_evaluate_script_produces_b2_report_fields():
    """The script's report must keep B1 schema and reflect B2 expansion."""
    report = run_evaluate()
    assert "candidate_records_by_family" in report
    families = report["candidate_records_by_family"]
    for family in B2_CANDIDATE_FAMILIES:
        assert family in families, f"missing family in report: {family}"
        assert families[family] >= 1


def test_b2_records_unblocked_by_quality_status():
    """No B2 record should be blocked (needs_human_review) since none was
    needed to meet the acceptance gates."""
    report = run_evaluate()
    blocked = report["records_blocked_by_quality_status"]
    for family in B2_CANDIDATE_FAMILIES:
        assert blocked.get(family, 0) == 0
