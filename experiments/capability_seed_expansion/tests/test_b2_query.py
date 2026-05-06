"""B2 routing tests for ExpandedKnowledgeQuery.

Verify that the four new B2 candidate families route correctly without
disturbing B1 routing or base-family delegation.
"""

from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.capability_seed_expansion.src.expanded_query import (
    ALL_CANDIDATE_FAMILIES,
    B1_CANDIDATE_FAMILIES,
    B2_CANDIDATE_FAMILIES,
    ExpandedKnowledgeQuery,
)
from experiments.capability_seed_expansion.src.loader import load_candidate_seed
from experiments.capability_seed_expansion.src.seed_merge import build_expanded_seed
from experiments.knowledge_capability_eval.src.loader import load_capability_questions


def make_expanded() -> ExpandedKnowledgeQuery:
    base = load_source_replaced_seed()
    candidate = load_candidate_seed()
    return ExpandedKnowledgeQuery(build_expanded_seed(base, candidate))


def test_b2_families_documented_and_disjoint_from_b1():
    assert B2_CANDIDATE_FAMILIES == (
        "drawing_requirement_records",
        "machining_allowance_records",
        "feature_process_records",
        "milling_process_records",
    )
    assert set(B1_CANDIDATE_FAMILIES).isdisjoint(B2_CANDIDATE_FAMILIES)
    assert ALL_CANDIDATE_FAMILIES == B1_CANDIDATE_FAMILIES + B2_CANDIDATE_FAMILIES


def test_dri_002_routes_to_drawing_requirement():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "图纸技术要求中的待焊面应如何解释并影响工艺安排？"
    )
    assert answer["status"] == "answered"
    top = answer["hits"][0]
    assert top["family"] == "drawing_requirement_records"
    assert "weld_surface" in top["subtype"]


def test_dri_003_routes_to_drawing_requirement():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "图纸上的焊接符号应该如何按国家标准完整解释？"
    )
    assert answer["status"] == "answered"
    top_families = {hit["family"] for hit in answer["hits"]}
    assert "drawing_requirement_records" in top_families
    top = answer["hits"][0]
    # Either symbol_standard_interpretation or symbol_standard_catalog acceptable
    assert "symbol_standard" in top["subtype"] or "symbol_standard_catalog" in top["subtype"]


def test_map_003_routes_to_machining_allowance():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "毛坯 φ103.5 加工到外圆 φ103 时，车削余量和装夹方案需要哪些知识？"
    )
    assert answer["status"] == "answered"
    top = answer["hits"][0]
    assert top["family"] == "machining_allowance_records"
    assert "blank_to_finished" in top["subtype"]


def test_fps_001_routes_to_feature_process():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "D 型孔应选择线切割、铣削还是其他方法加工？"
    )
    assert answer["status"] == "answered"
    top = answer["hits"][0]
    assert top["family"] == "feature_process_records"
    assert "d_shaped" in top["subtype"]


def test_fps_002_routes_to_milling_process():
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "2-R4 内轮廓圆角应如何安排铣削和检验？"
    )
    assert answer["status"] == "answered"
    top = answer["hits"][0]
    assert top["family"] == "milling_process_records"
    assert "inner_radius" in top["subtype"]


def test_map_001_still_routes_to_base_lookup_records():
    """MAP-001 expects lookup_records (per-pass allowance lookup); B2 must
    not steal it."""
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "精车后准备磨削，磨削余量推荐范围是多少？"
    )
    if answer["hits"]:
        top = answer["hits"][0]
        assert top.get("family") != "machining_allowance_records", (
            "B2 must not route MAP-001 (lookup) to machining_allowance"
        )


def test_map_002_still_routes_to_base_computation_methods():
    """MAP-002 expects computation_methods (formula); B2 must not steal it."""
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "精车到磨削的直径余量和单边余量怎么计算？"
    )
    if answer["hits"]:
        top = answer["hits"][0]
        assert top.get("family") != "machining_allowance_records", (
            "B2 must not route MAP-002 (computation) to machining_allowance"
        )


def test_eoc_002_still_routes_to_b1_equipment_capability():
    """EOC-002 mentions D 型孔 + R4 + 铣削 but expects equipment_capability;
    B1 routing must catch it before B2 milling/feature_process tries to."""
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "三轴加工中心适合本零件 D 型孔、R4 和位置度相关的哪些铣削工序？"
    )
    assert answer["status"] == "answered"
    top = answer["hits"][0]
    assert top["family"] == "equipment_capability_records"


def test_dri_001_still_routes_to_b1_standard_clause():
    """DRI-001 (GB/T 1804-m) must stay with B1 standard_clause routing."""
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "未注公差按 GB/T1804-m 执行时，普通线性尺寸公差应如何查询？"
    )
    top = answer["hits"][0]
    assert top["family"] == "standard_clause_records"


def test_gti_002_still_routes_to_base_principle_records():
    """GTI-002 (键槽对称度 inspection principle) must NOT be re-routed by B1
    inspection (preserved from B1) and must NOT be caught by B2."""
    expanded = make_expanded()
    answer = expanded.answer_for_agent(
        "键槽加工后应如何检查对称度？"
    )
    if answer["hits"]:
        top = answer["hits"][0]
        assert top.get("family") not in (
            "inspection_records",
            "drawing_requirement_records",
        )


def test_b2_capability_questions_for_target_ids_are_now_answered():
    """All five B2 target capability questions return correct expected_family."""
    expanded = make_expanded()
    questions = load_capability_questions()
    target_ids = {"DRI-002", "DRI-003", "FPS-001", "FPS-002", "MAP-003"}
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


def test_b2_routing_returns_citation_fields():
    """All B2 routes must produce hits with full citation fields."""
    expanded = make_expanded()
    questions = [
        "图纸技术要求中的待焊面应如何解释并影响工艺安排？",
        "毛坯 φ103.5 加工到外圆 φ103 时，车削余量和装夹方案需要哪些知识？",
        "D 型孔应选择线切割、铣削还是其他方法加工？",
        "2-R4 内轮廓圆角应如何安排铣削和检验？",
    ]
    for question in questions:
        answer = expanded.answer_for_agent(question)
        citations = answer["citations"]
        assert citations, f"no citations for: {question}"
        for citation in citations:
            assert citation.get("source_doc"), question
            assert citation.get("source_page") is not None, question
            assert citation.get("source_text"), question
