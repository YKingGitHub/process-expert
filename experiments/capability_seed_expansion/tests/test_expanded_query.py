"""Contract tests for ExpandedKnowledgeQuery — B1 candidate-family adapter."""

from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.agent_query_eval.src.query_api import KnowledgeQuery
from experiments.capability_seed_expansion.src.expanded_query import (
    ExpandedKnowledgeQuery,
    B1_CANDIDATE_FAMILIES,
)
from experiments.capability_seed_expansion.src.loader import load_candidate_seed
from experiments.capability_seed_expansion.src.seed_merge import build_expanded_seed
from experiments.knowledge_capability_eval.src.loader import load_capability_questions


def make_expanded() -> ExpandedKnowledgeQuery:
    base = load_source_replaced_seed()
    candidate = load_candidate_seed()
    return ExpandedKnowledgeQuery(build_expanded_seed(base, candidate))


def make_baseline() -> KnowledgeQuery:
    return KnowledgeQuery(load_source_replaced_seed())


def test_b1_families_are_three_documented_candidates():
    assert B1_CANDIDATE_FAMILIES == (
        "standard_clause_records",
        "inspection_records",
        "equipment_capability_records",
    )


def test_answer_shape_is_compatible_with_base_query():
    expanded = make_expanded()
    answer = expanded.answer_for_agent("φ50H7 的孔上下偏差是多少?")
    for field in ("intent", "status", "hits", "citations", "warnings"):
        assert field in answer, f"missing field: {field}"


def test_base_family_questions_still_route_through_knowledge_query():
    baseline = make_baseline()
    expanded = make_expanded()
    questions = [
        "轴类零件制定工艺路线时基准应如何选择?",
        "尺寸链封闭环基本尺寸怎么计算?",
        "有没有轴类零件工艺过程卡案例?",
    ]
    for question in questions:
        base_answer = baseline.answer_for_agent(question)
        expanded_answer = expanded.answer_for_agent(question)
        assert expanded_answer["intent"] == base_answer["intent"], question
        base_top = base_answer["hits"][0]["id"] if base_answer["hits"] else None
        expanded_top = expanded_answer["hits"][0]["id"] if expanded_answer["hits"] else None
        assert expanded_top == base_top, (
            f"divergent top hit on base-family question: {question}"
        )


def test_standard_clause_question_returns_b1_record():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "未注公差按 GB/T1804-m 执行时, 普通线性尺寸公差应如何查询?"
    )
    assert answer["status"] == "answered"
    assert answer["hits"], "no hits for GB/T1804-m question"
    top = answer["hits"][0]
    assert top["knowledge_type"] == "standard_clause"
    assert top["family"] == "standard_clause_records"
    assert isinstance(top.get("result_json"), dict)
    assert top["result_json"].get("level_code") == "m"


def test_inspection_question_returns_b1_record_with_datum():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "图样上 φ0.1 B C 注出位置度的检验方法是什么? 基准如何处理?"
    )
    assert answer["status"] == "answered"
    assert answer["hits"], "no hits for position tolerance inspection question"
    top = answer["hits"][0]
    assert top["family"] == "inspection_records"
    guidance = top.get("guidance_json") or {}
    assert "inspection_method" in guidance
    assert "datum_basis" in guidance


def test_equipment_capability_question_returns_b1_record():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "三轴加工中心适合加工本零件的哪些特征? 数控车床 vs 加工中心如何分工?"
    )
    assert answer["status"] == "answered"
    assert answer["hits"], "no hits for equipment capability question"
    top_families = {hit["family"] for hit in answer["hits"]}
    assert "equipment_capability_records" in top_families


def test_equipment_route_assignment_question_returns_guidance():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "本零件每道工序应分配给数控车床、三轴加工中心还是普通车床?"
    )
    assert answer["status"] == "answered"
    top_ids = {hit["id"] for hit in answer["hits"]}
    assert "EQUIP-ROUTE-ASSIGN-001" in top_ids


def test_b1_candidate_hits_carry_citation_fields():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "未注公差按 GB/T1804-m 执行时, 普通线性尺寸公差应如何查询?"
    )
    citations = answer["citations"]
    assert citations
    for citation in citations:
        assert citation.get("source_doc")
        assert citation.get("source_page") is not None
        assert citation.get("source_text")


def test_capability_questions_for_b1_families_are_now_answered():
    expanded = make_expanded()
    questions = load_capability_questions()
    target_ids = {"DRI-001", "GTI-001", "GTI-003", "EOC-002", "EOC-003"}
    for question in questions:
        if question["id"] not in target_ids:
            continue
        answer = expanded.answer_for_agent(question["question"])
        assert answer["status"] == "answered", (
            f"{question['id']} expected answered, got {answer['status']}"
        )
        top_families = {hit["family"] for hit in answer["hits"]}
        assert question["expected_family"] in top_families, (
            f"{question['id']} expected family {question['expected_family']!r}, "
            f"got {top_families}"
        )


def test_unrelated_b1_question_does_not_pull_b1_record():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "尺寸链封闭环基本尺寸怎么计算?"
    )
    if answer["hits"]:
        top = answer["hits"][0]
        assert top.get("family") != "standard_clause_records"
        assert top.get("family") != "inspection_records"
        assert top.get("family") != "equipment_capability_records"
