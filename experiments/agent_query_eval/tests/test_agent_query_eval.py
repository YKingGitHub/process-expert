from __future__ import annotations

from experiments.agent_query_eval.src.data_loader import load_gold_seed, load_questions
from experiments.agent_query_eval.src.evaluator import evaluate_questions
from experiments.agent_query_eval.src.query_api import KnowledgeQuery


def make_query() -> KnowledgeQuery:
    return KnowledgeQuery(load_gold_seed())


def test_question_set_has_expected_coverage():
    questions = load_questions()

    assert len(questions) == 21
    assert {item["expected_intent"] for item in questions} >= {
        "principle_query",
        "lookup_query",
        "computation_query",
        "case_query",
        "mixed_query",
        "unknown_query",
    }


def test_intent_classifier_matches_gold():
    query = make_query()
    questions = load_questions()

    intents = {item["id"]: query.classify_intent(item["question"]).intent for item in questions}

    for item in questions:
        assert intents[item["id"]] == item["expected_intent"]


def test_lookup_query_returns_structured_result_and_citation():
    answer = make_query().answer_for_agent("φ50H7 的上下偏差是多少？")

    assert answer["intent"] == "lookup_query"
    assert answer["status"] == "answered"
    hit = answer["hits"][0]
    assert hit["knowledge_type"] == "lookup"
    assert hit["result_json"]["upper_deviation_mm"] == 0.025
    assert hit["result_json"]["lower_deviation_mm"] == 0.0
    assert answer["citations"][0]["source_text"]


def test_computation_query_returns_method_contract():
    answer = make_query().answer_for_agent("尺寸链封闭环基本尺寸怎么计算？")

    assert answer["intent"] == "computation_query"
    hit = answer["hits"][0]
    assert hit["knowledge_type"] == "computation"
    assert hit["method_id"] == "calculate_closed_loop_basic_size"
    assert hit["implementation_status"] == "not_implemented"
    assert hit["formula"]


def test_case_query_marks_reference_case():
    answer = make_query().answer_for_agent("有没有轴类零件工艺过程卡案例？")

    assert answer["intent"] == "case_query"
    hit = answer["hits"][0]
    assert hit["knowledge_type"] == "case"
    assert hit["reference_case"] is True
    assert hit["part_name"] == "输出轴"


def test_unknown_query_returns_candidate_type():
    answer = make_query().answer_for_agent("某张图纸上的焊接符号应该如何按国家标准完整解释？")

    assert answer["intent"] == "unknown_query"
    assert answer["status"] == "not_found"
    assert answer["candidate_type"] == "drawing_requirement_records"
    assert answer["warnings"][0]["code"] == "candidate_type"


def test_full_evaluation_passes_thresholds():
    report = evaluate_questions(load_questions(), make_query())

    assert report["intent_accuracy"] >= 0.9
    assert report["pass_rate"] >= 0.9
    assert all(item["passed"] for item in report["results"])
