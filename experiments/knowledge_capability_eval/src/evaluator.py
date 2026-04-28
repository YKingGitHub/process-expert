"""Capability-level evaluator for process knowledge readiness."""

from __future__ import annotations

from collections import defaultdict

from experiments.agent_query_eval.src.query_api import KnowledgeQuery


CORE_FAMILIES = {
    "principle_records",
    "lookup_records",
    "computation_methods",
    "case_records",
    "mixed",
}

KNOWLEDGE_TYPE_TO_FAMILY = {
    "principle": "principle_records",
    "lookup": "lookup_records",
    "computation": "computation_methods",
    "case": "case_records",
}

REQUIRED_QUESTION_FIELDS = {
    "id",
    "capability",
    "question",
    "expected_family",
    "expected_subtype",
    "expected_contract",
    "required",
}


def validate_question_set(questions: list[dict], min_capabilities: int = 7, min_questions: int = 3) -> list[str]:
    errors = []
    missing_by_id = {
        item.get("id", f"index:{index}"): sorted(REQUIRED_QUESTION_FIELDS - set(item))
        for index, item in enumerate(questions)
        if REQUIRED_QUESTION_FIELDS - set(item)
    }
    for question_id, missing in missing_by_id.items():
        errors.append(f"{question_id} missing fields: {', '.join(missing)}")

    by_capability = group_by_capability(questions)
    if len(by_capability) < min_capabilities:
        errors.append(f"expected at least {min_capabilities} capabilities, got {len(by_capability)}")
    for capability, items in sorted(by_capability.items()):
        if len(items) < min_questions:
            errors.append(f"{capability} expected at least {min_questions} questions, got {len(items)}")
    return errors


def validate_real_drawing_gap_map(gap_map: list[dict], questions: list[dict]) -> list[str]:
    errors = []
    capabilities = set(group_by_capability(questions))
    for index, gap in enumerate(gap_map):
        for field in ("source_need_id", "capability", "candidate_type", "gap_summary"):
            if field not in gap:
                errors.append(f"gap_map[{index}] missing {field}")
        capability = gap.get("capability")
        if capability and capability not in capabilities:
            errors.append(f"gap_map[{index}] capability not in question set: {capability}")
    return errors


def evaluate_capabilities(
    questions: list[dict],
    query: KnowledgeQuery,
    real_drawing_gap_map: list[dict] | None = None,
) -> dict:
    question_errors = validate_question_set(questions)
    gap_map_errors = validate_real_drawing_gap_map(real_drawing_gap_map or [], questions)
    if question_errors or gap_map_errors:
        return {
            "status": "invalid",
            "errors": question_errors + gap_map_errors,
            "question_count": len(questions),
            "results": [],
        }

    results = [evaluate_question(question, query) for question in questions]
    by_capability = summarize_by_capability(results)
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
        "real_drawing_gap_count_by_capability": summarize_real_drawing_gaps(real_drawing_gap_map or []),
        "results": results,
    }


def evaluate_question(question: dict, query: KnowledgeQuery) -> dict:
    answer = query.answer_for_agent(question["question"])
    hits = answer.get("hits", [])
    actual_family = infer_actual_family(answer)
    checks = check_contract(question, answer, actual_family)
    covered = all(check["passed"] for check in checks)
    gap_reason = "covered" if covered else first_failed_check(checks)

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


def check_contract(question: dict, answer: dict, actual_family: str | None) -> list[dict]:
    expected_family = question["expected_family"]
    expected_contract = question["expected_contract"]
    hits = answer.get("hits", [])
    top_hit = hits[0] if hits else {}

    checks = [
        {
            "name": "family_available",
            "passed": expected_family in CORE_FAMILIES,
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

    contract_check = contract_check_for(expected_contract, answer, top_hit)
    checks.append(contract_check)
    return checks


def contract_check_for(expected_contract: str, answer: dict, top_hit: dict) -> dict:
    citations = answer.get("citations", [])
    if expected_contract == "citation_contract":
        passed = bool(citations) and all(
            citation.get("source_page") is not None and citation.get("source_text")
            for citation in citations
        )
        actual = citations
    elif expected_contract == "lookup_result_contract":
        passed = isinstance(top_hit.get("result_json"), dict)
        actual = top_hit.get("result_json")
    elif expected_contract == "method_contract":
        passed = bool(top_hit.get("method_id")) and bool(top_hit.get("formula"))
        actual = {
            "method_id": top_hit.get("method_id"),
            "formula": top_hit.get("formula"),
            "implementation_status": top_hit.get("implementation_status"),
        }
    elif expected_contract == "implemented_calculation_contract":
        passed = top_hit.get("implementation_status") in {"implemented", "verified"}
        actual = top_hit.get("implementation_status")
    elif expected_contract == "case_reference_contract":
        passed = top_hit.get("reference_case") is True and bool(top_hit.get("route_summary"))
        actual = {
            "reference_case": top_hit.get("reference_case"),
            "route_summary": top_hit.get("route_summary"),
        }
    elif expected_contract == "mixed_reference_contract":
        hit_types = {hit.get("knowledge_type") for hit in answer.get("hits", [])}
        passed = len(hit_types) >= 2 or "case" in hit_types
        actual = sorted(item for item in hit_types if item)
    else:
        passed = False
        actual = "contract_not_implemented_in_current_baseline"

    return {
        "name": "expected_contract",
        "passed": passed,
        "expected": expected_contract,
        "actual": actual,
    }


def infer_actual_family(answer: dict) -> str | None:
    hits = answer.get("hits", [])
    if answer.get("intent") == "mixed_query" and hits:
        return "mixed"
    if not hits:
        return None
    return KNOWLEDGE_TYPE_TO_FAMILY.get(hits[0].get("knowledge_type"))


def summarize_by_capability(results: list[dict]) -> dict:
    grouped = defaultdict(list)
    for result in results:
        grouped[result["capability"]].append(result)

    summary = {}
    for capability, items in sorted(grouped.items()):
        covered = [item for item in items if item["covered"]]
        required_gaps = [item for item in items if item["required"] and not item["covered"]]
        summary[capability] = {
            "question_count": len(items),
            "covered_count": len(covered),
            "gap_count": len(items) - len(covered),
            "required_gap_count": len(required_gaps),
            "coverage_rate": round(len(covered) / max(len(items), 1), 4),
            "gap_ids": [item["id"] for item in items if not item["covered"]],
        }
    return summary


def summarize_real_drawing_gaps(gap_map: list[dict]) -> dict:
    counts = defaultdict(int)
    for gap in gap_map:
        counts[gap["capability"]] += 1
    return dict(sorted(counts.items()))


def group_by_capability(questions: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for question in questions:
        capability = question.get("capability")
        if capability:
            grouped[capability].append(question)
    return dict(grouped)


def first_failed_check(checks: list[dict]) -> str:
    for check in checks:
        if not check["passed"]:
            return check["name"]
    return "unknown"

