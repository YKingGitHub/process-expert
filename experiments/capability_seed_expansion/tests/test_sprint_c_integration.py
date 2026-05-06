"""Sprint C — capability evaluator integration tests.

After Sprint C Phase 1, the only previously-blocked capability question
(DCA-003 ``python_executable_tolerance_lookup``) routes to the new
``CM-TOL-LOOKUP-ISO-001`` computation_methods record, whose ``method_id``
is implemented in ``process_calc.tolerance_lookup_iso`` and verified by
unit tests against ISO 286-1 textbook values.
"""

from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.agent_query_eval.src.query_api import KnowledgeQuery
from experiments.capability_seed_expansion.src.expanded_evaluator import (
    compare_baseline_vs_expanded,
    evaluate_baseline,
    evaluate_expanded,
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


def make_reports():
    questions = load_capability_questions()
    gap_map = load_real_drawing_gap_map()
    base = load_source_replaced_seed()
    candidate = load_candidate_seed()
    expanded_seed = build_expanded_seed(base, candidate)
    baseline = evaluate_baseline(questions, KnowledgeQuery(base), gap_map)
    expanded = evaluate_expanded(
        questions, ExpandedKnowledgeQuery(expanded_seed), gap_map
    )
    delta = compare_baseline_vs_expanded(baseline, expanded)
    return baseline, expanded, delta


def test_sprint_c_closes_dca_003():
    """DCA-003 must transition from uncovered to covered after Sprint C."""
    baseline, expanded, delta = make_reports()
    baseline_dca_003 = next(r for r in baseline["results"] if r["id"] == "DCA-003")
    expanded_dca_003 = next(r for r in expanded["results"] if r["id"] == "DCA-003")
    assert baseline_dca_003["covered"] is False
    assert expanded_dca_003["covered"] is True
    assert expanded_dca_003["actual_family"] == "computation_methods"
    assert expanded_dca_003["top_hit_id"] == "CM-TOL-LOOKUP-ISO-001"


def test_sprint_c_drives_gap_count_to_zero():
    """All 21 capability questions are covered after Sprint C Phase 1."""
    _, expanded, _ = make_reports()
    assert expanded["gap_count"] == 0
    assert expanded["covered_count"] == 21
    assert expanded["coverage_rate"] == 1.0


def test_sprint_c_preserves_b1_b2_transitions():
    _, _, delta = make_reports()
    transition_ids = {
        t["id"] for t in delta["transitions"]
        if t["transition"] == "uncovered_to_covered"
    }
    # B1 transitions
    for tid in ("DRI-001", "GTI-001", "GTI-003", "EOC-002", "EOC-003"):
        assert tid in transition_ids, f"B1 transition {tid} regressed"
    # B2 transitions
    for tid in ("DRI-002", "DRI-003", "FPS-001", "FPS-002", "MAP-003"):
        assert tid in transition_ids, f"B2 transition {tid} regressed"
    # Sprint C transition
    assert "DCA-003" in transition_ids


def test_sprint_c_no_baseline_regression():
    _, _, delta = make_reports()
    regressions = [
        t for t in delta["transitions"] if t["transition"] == "covered_to_uncovered"
    ]
    assert regressions == [], f"Sprint C regressed: {regressions}"


def test_sprint_c_dca_003_satisfies_implemented_calculation_contract():
    """The contract check requires top_hit.implementation_status in
    {implemented, verified}."""
    _, expanded, _ = make_reports()
    dca_003 = next(r for r in expanded["results"] if r["id"] == "DCA-003")
    contract_check = next(
        c for c in dca_003["checks"] if c["name"] == "expected_contract"
    )
    assert contract_check["passed"] is True


def test_sprint_c_dca_001_002_verified_status_propagated():
    """DCA-001 / DCA-002 keep their baseline coverage; their seed records
    now report implementation_status=verified."""
    seed = load_source_replaced_seed()
    cm_by_method = {r["method_id"]: r for r in seed["computation_methods"]}
    assert cm_by_method["closed_loop_basic_size"]["implementation_status"] == "verified"
    assert cm_by_method["extreme_tolerance"]["implementation_status"] == "verified"
    assert cm_by_method["finish_to_grind_allowance"]["implementation_status"] == "verified"
    assert cm_by_method["tolerance_lookup_iso"]["implementation_status"] == "verified"


def test_sprint_c_real_drawing_gap_count_stable():
    """Sprint C does not affect real-drawing recovery count (DCA-003 is
    not in the real-drawing gap_map)."""
    _, _, delta = make_reports()
    assert delta["real_drawing_mapped_gap_covered_count"] == 5
    assert delta["real_drawing_mapped_gap_total"] == 7
