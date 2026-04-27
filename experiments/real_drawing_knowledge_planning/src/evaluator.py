"""Evaluate real drawing knowledge planning outputs."""

from __future__ import annotations


def compare_route_families(hypothesis: list[str], reference_route: dict) -> dict:
    reference = [item["operation"] for item in reference_route["operations"]]
    matched = multiset_intersection_count(hypothesis, reference)
    precision = matched / max(len(hypothesis), 1)
    recall = matched / max(len(reference), 1)
    return {
        "hypothesis": hypothesis,
        "reference": reference,
        "matched_count": matched,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "missing_from_hypothesis": subtract_multiset(reference, hypothesis),
        "extra_in_hypothesis": subtract_multiset(hypothesis, reference),
    }


def evaluate_drawing_analysis(drawing: dict) -> dict:
    text = str(drawing)
    checks = [
        token_check("outer_diameter", "φ103" in text),
        token_check("thickness", "30.5" in text),
        token_check("inner_profile_diameter", "φ34" in text),
        token_check("offset_15", "15" in text and "+0.3/0" in text),
        token_check("position_tolerance", "φ0.1" in text and "B" in text and "C" in text),
        token_check("general_tolerance", "GB/T1804" in text),
        token_check("weld_surface_requirements", "待焊面" in text),
        token_check("d_shaped_or_milled_inner_profile", "D型" in text or "D 型" in text or "D-shaped" in text),
    ]
    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "accepted" if not failed else "needs_review",
        "check_count": len(checks),
        "failed_count": len(failed),
        "checks": checks,
        "flags": [
            {
                "code": "missing_critical_drawing_feature",
                "feature": check["name"],
            }
            for check in failed
        ],
    }


def summarize_package(package: dict, route_eval: dict) -> dict:
    items = package["items"]
    usable = [item for item in items if not item["assessment"]["gap"]]
    return {
        "need_count": len(items),
        "usable_need_count": len(usable),
        "gap_count": package["gap_report"]["gap_count"],
        "blocking_gap_count": package["gap_report"]["blocking_gap_count"],
        "route_family_recall": route_eval["recall"],
        "route_family_precision": route_eval["precision"],
    }


def token_check(name: str, passed: bool) -> dict:
    return {"name": name, "passed": passed}


def multiset_intersection_count(left: list[str], right: list[str]) -> int:
    right_counts = counts(right)
    matched = 0
    for item in left:
        if right_counts.get(item, 0) > 0:
            matched += 1
            right_counts[item] -= 1
    return matched


def subtract_multiset(left: list[str], right: list[str]) -> list[str]:
    right_counts = counts(right)
    result = []
    for item in left:
        if right_counts.get(item, 0) > 0:
            right_counts[item] -= 1
        else:
            result.append(item)
    return result


def counts(values: list[str]) -> dict[str, int]:
    result = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result
