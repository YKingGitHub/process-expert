"""Evaluation harness for the Agent knowledge query POC."""

from __future__ import annotations

from .query_api import KnowledgeQuery


def evaluate_questions(questions: list[dict], query: KnowledgeQuery) -> dict:
    results = []
    for question in questions:
        answer = query.answer_for_agent(question["question"])
        checks = check_answer(question, answer)
        results.append(
            {
                "id": question["id"],
                "question": question["question"],
                "expected_intent": question["expected_intent"],
                "actual_intent": answer["intent"],
                "expected_status": question["expected_status"],
                "actual_status": answer["status"],
                "checks": checks,
                "passed": all(check["passed"] for check in checks),
                "answer": answer,
            }
        )

    passed = [item for item in results if item["passed"]]
    intent_correct = [
        item for item in results if item["expected_intent"] == item["actual_intent"]
    ]
    return {
        "question_count": len(questions),
        "passed_count": len(passed),
        "pass_rate": round(len(passed) / max(len(questions), 1), 4),
        "intent_accuracy": round(len(intent_correct) / max(len(questions), 1), 4),
        "results": results,
    }


def check_answer(question: dict, answer: dict) -> list[dict]:
    checks = [
        {
            "name": "intent",
            "passed": answer["intent"] == question["expected_intent"],
            "expected": question["expected_intent"],
            "actual": answer["intent"],
        },
        {
            "name": "status",
            "passed": answer["status"] == question["expected_status"],
            "expected": question["expected_status"],
            "actual": answer["status"],
        },
    ]

    if question["expected_status"] == "answered":
        checks.extend(check_answered_contract(question, answer))
    else:
        checks.append(
            {
                "name": "candidate_type_for_not_found",
                "passed": bool(answer.get("candidate_type")) or bool(answer.get("warnings")),
                "expected": "candidate_type or warning",
                "actual": answer.get("candidate_type") or answer.get("warnings"),
            }
        )
    return checks


def check_answered_contract(question: dict, answer: dict) -> list[dict]:
    expected_type = question["expected_knowledge_type"]
    hits = answer.get("hits", [])
    citations = answer.get("citations", [])
    checks = [
        {
            "name": "has_hits",
            "passed": bool(hits),
            "expected": "non-empty hits",
            "actual": len(hits),
        },
        {
            "name": "has_citations",
            "passed": bool(citations)
            and all(c.get("source_page") is not None and c.get("source_text") for c in citations),
            "expected": "source_page and source_text for every citation",
            "actual": citations,
        },
    ]

    if expected_type != "mixed":
        checks.append(
            {
                "name": "knowledge_type",
                "passed": bool(hits) and hits[0].get("knowledge_type") == expected_type,
                "expected": expected_type,
                "actual": hits[0].get("knowledge_type") if hits else None,
            }
        )
    else:
        hit_types = {hit.get("knowledge_type") for hit in hits}
        checks.append(
            {
                "name": "mixed_knowledge_types",
                "passed": len(hit_types) >= 2 or "case" in hit_types,
                "expected": "multiple relevant knowledge types",
                "actual": sorted(hit_types),
            }
        )

    if expected_type == "lookup":
        checks.append(
            {
                "name": "lookup_structured_result",
                "passed": bool(hits) and isinstance(hits[0].get("result_json"), dict),
                "expected": "result_json dict",
                "actual": hits[0].get("result_json") if hits else None,
            }
        )
    elif expected_type == "computation":
        checks.append(
            {
                "name": "computation_method_contract",
                "passed": bool(hits)
                and bool(hits[0].get("method_id"))
                and hits[0].get("implementation_status") in ("not_implemented", "prototype", "implemented", "verified"),
                "expected": "method_id plus implementation_status",
                "actual": hits[0] if hits else None,
            }
        )
    elif expected_type == "case":
        checks.append(
            {
                "name": "case_reference_boundary",
                "passed": bool(hits) and hits[0].get("reference_case") is True,
                "expected": "reference_case true",
                "actual": hits[0].get("reference_case") if hits else None,
            }
        )
    return checks
