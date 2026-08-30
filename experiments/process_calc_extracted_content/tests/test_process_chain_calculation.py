from __future__ import annotations

import json
from pathlib import Path

from experiments.process_calc_extracted_content.src.calculators import (
    analyze_cylinder_liner_allowance,
    analyze_explicit_grinding_allowance,
)
from experiments.process_calc_extracted_content.src.route_model import reconstruct_routes


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def load_process_cards():
    return json.loads(
        (FIXTURE_DIR / "process_cards_sample.json").read_text(encoding="utf-8")
    )


def test_cylinder_liner_finish_to_grind_allowance_is_calculable():
    routes = reconstruct_routes(load_process_cards())
    route = next(route for route in routes if route.canonical_part_name == "缸套")

    result = analyze_cylinder_liner_allowance(route)

    assert result["unit"] == "mm"
    assert result["steps"]
    assert not result["warnings"]
    assert result["result"]["inner_monotonic_non_decreasing"] is True
    assert result["result"]["outer_monotonic_non_increasing"] is True
    assert (
        result["result"]["inner_finish_to_grind_allowance"]["diameter_allowance"]
        == 0.8
    )
    assert (
        result["result"]["inner_finish_to_grind_allowance"]["single_side_allowance"]
        == 0.4
    )
    assert (
        result["result"]["outer_finish_to_grind_allowance"]["diameter_allowance"]
        == 0.8
    )
    assert (
        result["result"]["outer_finish_to_grind_allowance"]["single_side_allowance"]
        == 0.4
    )


def test_output_shaft_explicit_grinding_allowance_is_guarded_incomplete():
    routes = reconstruct_routes(load_process_cards())
    route = next(route for route in routes if route.canonical_part_name == "输出轴")

    result = analyze_explicit_grinding_allowance(route)

    assert result["unit"] == "mm"
    assert result["steps"]
    assert result["result"]["status"] == "needs_more_structured_final_dimension"
    allowances = result["result"]["explicit_allowances"]
    assert [item["value"] for item in allowances] == [0.8, 0.8]
    assert allowances[0]["later_grinding_steps"] == [7, 8]
    assert allowances[1]["later_grinding_steps"] == [7, 8]
