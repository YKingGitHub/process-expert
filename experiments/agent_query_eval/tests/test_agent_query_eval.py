from __future__ import annotations

import json
from pathlib import Path

from experiments.agent_query_eval.src.data_loader import (
    load_gold_seed,
    load_questions,
    load_source_replaced_seed,
)
from experiments.agent_query_eval.src.evaluator import evaluate_questions
from experiments.agent_query_eval.src.query_api import KnowledgeQuery


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT_PATH = EXPERIMENT_ROOT / "data" / "source_replacement_report.json"


def make_query() -> KnowledgeQuery:
    return KnowledgeQuery(load_source_replaced_seed())


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
    # Sprint C renamed the method_id to match the process_calc registry naming
    # policy ({module}_{operation} without the legacy ``calculate_`` prefix).
    assert hit["method_id"] == "closed_loop_basic_size"
    # Sprint C also flipped the implementation_status from not_implemented to
    # verified now that process_calc.closed_loop_basic_size is implemented and
    # textbook-verified.
    assert hit["implementation_status"] == "verified"
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


def test_original_gold_seed_still_passes_as_baseline():
    report = evaluate_questions(load_questions(), KnowledgeQuery(load_gold_seed()))

    assert report["intent_accuracy"] >= 0.9
    assert report["pass_rate"] >= 0.9
    assert all(item["passed"] for item in report["results"])


def test_source_replaced_seed_tracks_replacements_and_limits():
    seed = load_source_replaced_seed()
    report = json.loads(SOURCE_REPORT_PATH.read_text(encoding="utf-8"))

    replaced = {
        record["id"]
        for records in seed.values()
        if isinstance(records, list)
        for record in records
        if record.get("source_replacement_status") == "source_pdf_vlm_replaced"
    }

    assert report["replaced_count"] == 11
    assert report["retained_manual_count"] == 0
    assert "PR-DATUM-AXIS-001" in replaced
    assert "PR-THIN-WALL-001" in replaced
    assert "PR-INSPECTION-KEYSLOT-001" in replaced
    assert "LU-ALLOW-GRIND-001" in replaced
    assert "CM-ALLOW-FINISH-GRIND-001" in replaced
    assert "CASE-CYLINDER-LINER-001" in replaced

    keyslot = next(
        item for item in seed["principle_records"] if item["id"] == "PR-INSPECTION-KEYSLOT-001"
    )
    assert keyslot["source_replacement_status"] == "source_pdf_vlm_replaced"
    assert keyslot["extraction_source"]["kind"] == "source_pdf_vlm_prose"
    assert keyslot["extraction_source"]["fixture"].endswith("p107_principles.json")
    assert "偏摆仪及量块" in keyslot["source_text"]
    assert report["source_quality"]["status"] == "passed_with_flags"
    assert report["prose_quality"]["status"] == "accepted"
    assert report["prose_quality"]["fixture_count"] == 1


def test_source_replaced_allowance_comes_from_vlm_dimensions():
    seed = load_source_replaced_seed()
    lookup = next(item for item in seed["lookup_records"] if item["id"] == "LU-ALLOW-GRIND-001")
    method = next(
        item for item in seed["computation_methods"] if item["id"] == "CM-ALLOW-FINISH-GRIND-001"
    )

    assert lookup["source_replacement_status"] == "source_pdf_vlm_replaced"
    assert lookup["result_json"]["diameter_allowance_mm"] == 0.8
    assert lookup["result_json"]["single_side_allowance_mm"] == 0.4
    assert "φ279.2 ±0.05" in lookup["source_text"]
    assert "φ280 +0.08/0" in lookup["source_text"]
    assert method["example_json"]["inner_finish_to_grind_allowance"]["status"] == "passed"
