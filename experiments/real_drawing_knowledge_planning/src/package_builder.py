"""Build a knowledge package and gap report from planned needs."""

from __future__ import annotations

from experiments.agent_query_eval.src.query_api import KnowledgeQuery


def build_knowledge_package(needs: list[dict], query: KnowledgeQuery, seed: dict) -> dict:
    raw_by_id = index_seed(seed)
    items = []
    gaps = []

    for need in needs:
        answer = query.answer_for_agent(need["question"])
        enriched_hits = [enrich_hit(hit, raw_by_id) for hit in answer.get("hits", [])]
        assessment = assess_need(need, answer, enriched_hits)
        item = {
            "need": need,
            "answer": {**answer, "hits": enriched_hits},
            "assessment": assessment,
        }
        items.append(item)
        if assessment["gap"]:
            gaps.append(
                {
                    "need_id": need["id"],
                    "question": need["question"],
                    "severity": "blocking" if need["required"] else "non_blocking",
                    "reason": assessment["reason"],
                    "candidate_type": need.get("candidate_type") or answer.get("candidate_type"),
                }
            )

    return {
        "items": items,
        "gap_report": {
            "gap_count": len(gaps),
            "blocking_gap_count": sum(1 for gap in gaps if gap["severity"] == "blocking"),
            "gaps": gaps,
        },
    }


def index_seed(seed: dict) -> dict[str, dict]:
    result = {}
    for records in seed.values():
        if not isinstance(records, list):
            continue
        for record in records:
            if "id" in record:
                result[record["id"]] = record
    return result


def enrich_hit(hit: dict, raw_by_id: dict[str, dict]) -> dict:
    raw = raw_by_id.get(hit.get("id"), {})
    enriched = dict(hit)
    for key in ("source_replacement_status", "extraction_source", "route_json"):
        if key in raw:
            enriched[key] = raw[key]
    return enriched


def assess_need(need: dict, answer: dict, hits: list[dict]) -> dict:
    if not hits:
        return {"gap": True, "reason": "not_found"}
    if need["expected_knowledge_type"] == "candidate":
        return {"gap": True, "reason": "candidate_type_not_implemented"}
    if answer["intent"] != need["expected_intent"] and need["expected_intent"] != "mixed_query":
        return {"gap": True, "reason": f"intent_mismatch:{answer['intent']}"}
    if need["expected_knowledge_type"] != "mixed" and hits[0].get("knowledge_type") != need["expected_knowledge_type"]:
        return {"gap": True, "reason": f"knowledge_type_mismatch:{hits[0].get('knowledge_type')}"}
    if any(hit.get("quality_status") == "needs_human_review" for hit in hits):
        return {"gap": True, "reason": "top_results_include_needs_human_review"}
    if not any(hit.get("source_replacement_status") == "source_pdf_vlm_replaced" for hit in hits):
        return {"gap": True, "reason": "no_source_replaced_hit"}
    return {"gap": False, "reason": "usable"}
