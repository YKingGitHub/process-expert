from __future__ import annotations

import json
from pathlib import Path

from experiments.process_calc_extracted_content.src.route_model import (
    normalize_operation,
    reconstruct_routes,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def load_json(name: str):
    path = FIXTURE_DIR / name
    assert path.exists(), f"missing fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def route_by_part(routes, part_name: str):
    matches = [route for route in routes if route.canonical_part_name == part_name]
    assert len(matches) == 1
    return matches[0]


def test_operation_category_normalization_covers_known_names():
    assert normalize_operation("下料") == "blank_preparation"
    assert normalize_operation("粗车") == "rough_or_general_machining"
    assert normalize_operation("铣、钻、镗（连杆体）") == "rough_or_general_machining"
    assert normalize_operation("精镗") == "finish_machining"
    assert normalize_operation("检") == "inspection"
    assert normalize_operation("入库") == "storage"


def test_output_shaft_continuation_route_is_merged():
    records = load_json("process_cards_sample.json")
    expected = load_json("expected_cases.json")["output_shaft"]

    route = route_by_part(reconstruct_routes(records), expected["canonical_part_name"])

    assert route.source_part_names == expected["source_part_names"]
    assert route.step_numbers == expected["expected_step_numbers"]
    assert len(route.steps) == expected["expected_step_count"]
    assert set(expected["expected_categories"]).issubset(route.categories)
    assert any(warning["code"] == "continuation_merged" for warning in route.warnings)
    assert not any(
        warning["code"] == "non_continuous_step_sequence"
        for warning in route.warnings
    )


def test_seal_positioning_sleeve_continuation_route_is_merged():
    records = load_json("process_cards_sample.json")
    expected = load_json("expected_cases.json")["seal_positioning_sleeve"]

    route = route_by_part(reconstruct_routes(records), expected["canonical_part_name"])

    assert route.source_part_names == expected["source_part_names"]
    assert route.step_numbers == expected["expected_step_numbers"]
    assert len(route.steps) == expected["expected_step_count"]
    assert set(expected["expected_categories"]).issubset(route.categories)
    assert any(warning["code"] == "continuation_merged" for warning in route.warnings)
    assert not any(
        warning["code"] == "non_continuous_step_sequence"
        for warning in route.warnings
    )


def test_all_selected_routes_have_machine_readable_warnings():
    records = load_json("process_cards_sample.json")
    routes = reconstruct_routes(records)

    for route in routes:
        for warning in route.warnings:
            assert "code" in warning
            assert isinstance(warning["code"], str)
