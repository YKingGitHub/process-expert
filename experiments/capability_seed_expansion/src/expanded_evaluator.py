"""B1 + B2 expanded evaluator — extends the base capability evaluator with
seven candidate families and their per-question contract checks.

Strict separation: ``evaluate_baseline`` keeps the base CORE_FAMILIES/contract
table untouched, so the baseline ``gap_count_by_capability`` matches the
Sprint A baseline exactly (11/21). ``evaluate_expanded`` swaps in extended
sets that include B1 (3 families, 3 contracts) and B2 (4 families, 3
contracts).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from experiments.knowledge_capability_eval.src import evaluator as base_eval


EXPANDED_CORE_FAMILIES = base_eval.CORE_FAMILIES | {
    # B1
    "standard_clause_records",
    "inspection_records",
    "equipment_capability_records",
    # B2
    "drawing_requirement_records",
    "machining_allowance_records",
    "feature_process_records",
    "milling_process_records",
}

EXPANDED_KNOWLEDGE_TYPE_TO_FAMILY = {
    **base_eval.KNOWLEDGE_TYPE_TO_FAMILY,
    # B1
    "standard_clause": "standard_clause_records",
    "inspection": "inspection_records",
    "equipment_capability": "equipment_capability_records",
    # B2
    "drawing_requirement": "drawing_requirement_records",
    "machining_allowance": "machining_allowance_records",
    "feature_process": "feature_process_records",
    "milling_process": "milling_process_records",
}


def evaluate_baseline(questions, query, real_drawing_gap_map=None) -> dict:
    """Run the original base evaluator without modification."""
    return base_eval.evaluate_capabilities(questions, query, real_drawing_gap_map)


def evaluate_expanded(questions, query, real_drawing_gap_map=None) -> dict:
    """Run the evaluator with B1 candidate families and contracts wired in.

    Implementation note: the base evaluator's ``check_contract`` reads the
    module-level ``CORE_FAMILIES``, so we run the questions through a thin
    re-implementation here rather than monkey-patching the base module.
    """
    question_errors = base_eval.validate_question_set(questions)
    gap_map_errors = base_eval.validate_real_drawing_gap_map(
        real_drawing_gap_map or [], questions
    )
    if question_errors or gap_map_errors:
        return {
            "status": "invalid",
            "errors": question_errors + gap_map_errors,
            "question_count": len(questions),
            "results": [],
        }

    results = [_evaluate_question_expanded(question, query) for question in questions]
    by_capability = base_eval.summarize_by_capability(results)
    gap_count_by_capability = {
        capability: summary["gap_count"]
        for capability, summary in sorted(by_capability.items())
    }
    covered = [item for item in results if item["covered"]]
    gaps = [item for item in results if not item["covered"]]

    return {
        "status": "valid",
        "question_count": len(results),
        "capability_count": len(by_capability),
        "covered_count": len(covered),
        "gap_count": len(gaps),
        "coverage_rate": round(len(covered) / max(len(results), 1), 4),
        "gap_count_by_capability": gap_count_by_capability,
        "capability_summary": by_capability,
        "real_drawing_gap_map": real_drawing_gap_map or [],
        "real_drawing_gap_count_by_capability": base_eval.summarize_real_drawing_gaps(
            real_drawing_gap_map or []
        ),
        "results": results,
    }


def _evaluate_question_expanded(question: dict, query) -> dict:
    answer = query.answer_for_agent(question["question"])
    hits = answer.get("hits", [])
    actual_family = _infer_actual_family_expanded(answer)
    checks = _check_contract_expanded(question, answer, actual_family)
    covered = all(check["passed"] for check in checks)
    gap_reason = "covered" if covered else base_eval.first_failed_check(checks)

    return {
        "id": question["id"],
        "capability": question["capability"],
        "question": question["question"],
        "required": question["required"],
        "expected_family": question["expected_family"],
        "expected_subtype": question["expected_subtype"],
        "expected_contract": question["expected_contract"],
        "actual_intent": answer.get("intent"),
        "actual_status": answer.get("status"),
        "actual_family": actual_family,
        "candidate_type": question.get("candidate_type") or answer.get("candidate_type"),
        "top_hit_id": hits[0].get("id") if hits else None,
        "covered": covered,
        "gap_reason": gap_reason,
        "checks": checks,
    }


def _infer_actual_family_expanded(answer: dict) -> str | None:
    hits = answer.get("hits", [])
    if answer.get("intent") == "mixed_query" and hits:
        return "mixed"
    if not hits:
        return None
    top = hits[0]
    if top.get("family") in EXPANDED_CORE_FAMILIES:
        return top["family"]
    return EXPANDED_KNOWLEDGE_TYPE_TO_FAMILY.get(top.get("knowledge_type"))


def _check_contract_expanded(
    question: dict, answer: dict, actual_family: str | None
) -> list[dict]:
    expected_family = question["expected_family"]
    expected_contract = question["expected_contract"]
    hits = answer.get("hits", [])
    top_hit = hits[0] if hits else {}

    checks = [
        {
            "name": "family_available",
            "passed": expected_family in EXPANDED_CORE_FAMILIES,
            "expected": "implemented core family",
            "actual": expected_family,
        },
        {
            "name": "family_match",
            "passed": actual_family == expected_family,
            "expected": expected_family,
            "actual": actual_family,
        },
    ]

    contract_check = _contract_check_expanded(expected_contract, answer, top_hit)
    checks.append(contract_check)
    return checks


def _contract_check_expanded(
    expected_contract: str, answer: dict, top_hit: dict
) -> dict:
    handler = _EXPANDED_CONTRACTS.get(expected_contract)
    if handler is not None:
        passed, actual = handler(answer, top_hit)
        return {
            "name": "expected_contract",
            "passed": passed,
            "expected": expected_contract,
            "actual": actual,
        }
    return base_eval.contract_check_for(expected_contract, answer, top_hit)


def _check_standard_clause_lookup(answer: dict, top_hit: dict) -> tuple[bool, dict]:
    citations = answer.get("citations", [])
    rj = top_hit.get("result_json")
    gj = top_hit.get("guidance_json")
    payload = rj if isinstance(rj, dict) else gj if isinstance(gj, dict) else None
    has_standard = isinstance(payload, dict) and bool(payload.get("standard"))
    has_level = isinstance(payload, dict) and bool(
        payload.get("level_code") or payload.get("level_codes") or payload.get("level_choices")
    )
    has_citations = bool(citations) and all(
        c.get("source_page") is not None and c.get("source_text") for c in citations
    )
    passed = has_standard and has_level and has_citations
    return passed, {
        "has_standard": has_standard,
        "has_level": has_level,
        "has_citations": has_citations,
    }


def _check_inspection_with_datum(answer: dict, top_hit: dict) -> tuple[bool, dict]:
    citations = answer.get("citations", [])
    guidance = top_hit.get("guidance_json")
    has_method = isinstance(guidance, dict) and bool(guidance.get("inspection_method"))
    has_datum = isinstance(guidance, dict) and bool(guidance.get("datum_basis"))
    has_citations = bool(citations) and all(
        c.get("source_page") is not None and c.get("source_text") for c in citations
    )
    passed = has_method and has_datum and has_citations
    return passed, {
        "has_inspection_method": has_method,
        "has_datum_basis": has_datum,
        "has_citations": has_citations,
    }


def _check_equipment_operation_match(answer: dict, top_hit: dict) -> tuple[bool, dict]:
    citations = answer.get("citations", [])
    rj = top_hit.get("result_json")
    gj = top_hit.get("guidance_json")
    has_equipment_payload = isinstance(rj, dict) and (
        bool(rj.get("equipment_name")) and bool(rj.get("typical_operations"))
    )
    has_assignment_payload = isinstance(gj, dict) and bool(gj.get("assignment_rules"))
    payload_ok = has_equipment_payload or has_assignment_payload
    has_citations = bool(citations) and all(
        c.get("source_page") is not None and c.get("source_text") for c in citations
    )
    passed = payload_ok and has_citations
    return passed, {
        "has_equipment_payload": has_equipment_payload,
        "has_assignment_payload": has_assignment_payload,
        "has_citations": has_citations,
    }


def _check_feature_to_process(answer: dict, top_hit: dict) -> tuple[bool, dict]:
    """B2 — FPS-001 / FPS-002 contract: top hit's result_json must declare
    `feature_kind` and a non-empty `recommended_processes` list."""
    citations = answer.get("citations", [])
    rj = top_hit.get("result_json")
    has_feature = isinstance(rj, dict) and bool(rj.get("feature_kind"))
    has_processes = (
        isinstance(rj, dict)
        and isinstance(rj.get("recommended_processes"), list)
        and len(rj["recommended_processes"]) >= 1
    )
    has_citations = bool(citations) and all(
        c.get("source_page") is not None and c.get("source_text") for c in citations
    )
    passed = has_feature and has_processes and has_citations
    return passed, {
        "has_feature_kind": has_feature,
        "has_recommended_processes": has_processes,
        "has_citations": has_citations,
    }


def _check_allowance_planning(answer: dict, top_hit: dict) -> tuple[bool, dict]:
    """B2 — MAP-003 contract: top hit's result_json must declare a
    `step_pair` (predecessor + successor) plus at least one numeric allowance
    field (`single_side_allowance_mm`, `typical_single_side_allowance_range_mm`,
    or per-surface `single_side_allowance_mm`)."""
    citations = answer.get("citations", [])
    rj = top_hit.get("result_json")
    has_step_pair = (
        isinstance(rj, dict)
        and isinstance(rj.get("step_pair"), dict)
        and bool(rj["step_pair"].get("predecessor"))
        and bool(rj["step_pair"].get("successor"))
    )
    has_value = False
    if isinstance(rj, dict):
        if rj.get("single_side_allowance_mm") is not None:
            has_value = True
        elif rj.get("typical_single_side_allowance_range_mm") is not None:
            has_value = True
        elif isinstance(rj.get("surfaces"), list):
            has_value = any(
                isinstance(s, dict) and s.get("single_side_allowance_mm") is not None
                for s in rj["surfaces"]
            )
    has_citations = bool(citations) and all(
        c.get("source_page") is not None and c.get("source_text") for c in citations
    )
    passed = has_step_pair and has_value and has_citations
    return passed, {
        "has_step_pair": has_step_pair,
        "has_allowance_value": has_value,
        "has_citations": has_citations,
    }


def _check_drawing_requirement_interpretation(
    answer: dict, top_hit: dict
) -> tuple[bool, dict]:
    """B2 — DRI-002 / DRI-003 contract: top hit's guidance_json must declare
    `interpretation` and `applies_to`."""
    citations = answer.get("citations", [])
    gj = top_hit.get("guidance_json")
    has_interpretation = isinstance(gj, dict) and bool(gj.get("interpretation"))
    has_applies = isinstance(gj, dict) and bool(gj.get("applies_to"))
    has_citations = bool(citations) and all(
        c.get("source_page") is not None and c.get("source_text") for c in citations
    )
    passed = has_interpretation and has_applies and has_citations
    return passed, {
        "has_interpretation": has_interpretation,
        "has_applies_to": has_applies,
        "has_citations": has_citations,
    }


_EXPANDED_CONTRACTS: dict[str, Callable[[dict, dict], tuple[bool, dict]]] = {
    # B1
    "standard_clause_lookup": _check_standard_clause_lookup,
    "inspection_method_with_datum": _check_inspection_with_datum,
    "equipment_operation_match": _check_equipment_operation_match,
    # B2
    "feature_to_process_contract": _check_feature_to_process,
    "allowance_planning_contract": _check_allowance_planning,
    "drawing_requirement_interpretation": _check_drawing_requirement_interpretation,
}


def compare_baseline_vs_expanded(
    baseline_report: dict, expanded_report: dict
) -> dict:
    """Build the audit-friendly delta document required by WO-B1-003."""
    if baseline_report.get("status") != "valid" or expanded_report.get("status") != "valid":
        return {
            "status": "invalid_input",
            "baseline_status": baseline_report.get("status"),
            "expanded_status": expanded_report.get("status"),
        }

    baseline_by_id = {r["id"]: r for r in baseline_report["results"]}
    expanded_by_id = {r["id"]: r for r in expanded_report["results"]}

    gap_delta_by_capability: dict[str, int] = defaultdict(int)
    capabilities = sorted(baseline_report["gap_count_by_capability"])
    for capability in capabilities:
        delta = (
            baseline_report["gap_count_by_capability"].get(capability, 0)
            - expanded_report["gap_count_by_capability"].get(capability, 0)
        )
        gap_delta_by_capability[capability] = delta

    transitions = []
    for question_id, baseline_result in baseline_by_id.items():
        expanded_result = expanded_by_id.get(question_id)
        if expanded_result is None:
            continue
        if not baseline_result["covered"] and expanded_result["covered"]:
            transitions.append(
                {
                    "id": question_id,
                    "capability": expanded_result["capability"],
                    "expected_family": expanded_result["expected_family"],
                    "expected_contract": expanded_result["expected_contract"],
                    "expanded_top_hit_id": expanded_result["top_hit_id"],
                    "transition": "uncovered_to_covered",
                }
            )
        elif baseline_result["covered"] and not expanded_result["covered"]:
            transitions.append(
                {
                    "id": question_id,
                    "capability": expanded_result["capability"],
                    "transition": "covered_to_uncovered",
                    "gap_reason": expanded_result["gap_reason"],
                }
            )

    real_drawing_mapped_gap_covered_count = _count_real_drawing_recoveries(
        expanded_report, transitions
    )

    return {
        "status": "valid",
        "baseline_gap_count": baseline_report["gap_count"],
        "expanded_gap_count": expanded_report["gap_count"],
        "gap_reduction": baseline_report["gap_count"] - expanded_report["gap_count"],
        "gap_delta_by_capability": dict(gap_delta_by_capability),
        "transitions": transitions,
        "real_drawing_mapped_gap_covered_count": real_drawing_mapped_gap_covered_count,
        "real_drawing_mapped_gap_total": len(
            expanded_report.get("real_drawing_gap_map", [])
        ),
    }


def _count_real_drawing_recoveries(
    expanded_report: dict, transitions: list[dict]
) -> int:
    """Count distinct real-drawing gap_map entries whose (candidate_type,
    capability) pair now has at least one B1 uncovered_to_covered transition.

    This counts gaps, not transitions: two questions in the same family +
    capability count as one gap recovery, matching the WO-B1-003 design intent
    that ``real_drawing_mapped_gap_covered_count`` enumerates real-drawing
    knowledge needs, not capability-eval question IDs.
    """
    gap_map = expanded_report.get("real_drawing_gap_map") or []
    if not gap_map:
        return 0
    recovered_keys = {
        (transition["expected_family"], transition["capability"])
        for transition in transitions
        if transition["transition"] == "uncovered_to_covered"
    }
    recovered = 0
    for entry in gap_map:
        key = (entry.get("candidate_type"), entry.get("capability"))
        if key in recovered_keys:
            recovered += 1
    return recovered


def candidate_records_by_family(candidate_seed: dict[str, list[dict]]) -> dict:
    return {family: len(records) for family, records in candidate_seed.items()}


def records_blocked_by_quality_status(candidate_seed: dict[str, list[dict]]) -> dict:
    blocked = defaultdict(int)
    for family, records in candidate_seed.items():
        for record in records:
            if record.get("quality_status") == "needs_human_review":
                blocked[family] += 1
    return dict(blocked)
