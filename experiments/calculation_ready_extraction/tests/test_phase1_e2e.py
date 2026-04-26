from __future__ import annotations

import sqlite3
from pathlib import Path

from experiments.calculation_ready_extraction.src.calculation import (
    calculate_cylinder_liner_allowance,
)
from experiments.calculation_ready_extraction.src.db_builder import build_db
from experiments.calculation_ready_extraction.src.loader import (
    load_p108_gold,
    load_vlm_pages,
)
from experiments.calculation_ready_extraction.src.quality_gate import evaluate_pages
from experiments.calculation_ready_extraction.src.query_api import (
    get_process_route,
    get_step_dimensions,
)
from experiments.calculation_ready_extraction.src.route_merge import merge_routes


def route_by_part(routes, part_name):
    matches = [route for route in routes if route.part_name == part_name]
    assert len(matches) == 1
    return matches[0]


def test_quality_gate_detects_known_phase1_flags():
    pages = load_vlm_pages()
    quality = evaluate_pages(pages, gold_payloads=[load_p108_gold()])
    codes = {flag["code"] for flag in quality["flags"]}

    assert quality["status"] == "passed_with_flags"
    assert "gold_dimension_mismatch" in codes
    assert "zero_step_card" in codes
    assert "continuation_part_missing" in codes


def test_routes_merge_continuation_pages():
    routes = merge_routes(load_vlm_pages())

    output_shaft = route_by_part(routes, "输出轴")
    seal_sleeve = route_by_part(routes, "密封件定位套")
    cylinder_liner = route_by_part(routes, "缸套")

    assert output_shaft.step_numbers == list(range(1, 13))
    assert output_shaft.source_pages == [106, 107]
    assert seal_sleeve.step_numbers == list(range(1, 14))
    assert seal_sleeve.source_pages == [109, 110]
    assert cylinder_liner.step_numbers == list(range(1, 14))
    assert cylinder_liner.source_pages == [108]


def test_cylinder_liner_allowance_calculates_from_vlm_json():
    routes = merge_routes(load_vlm_pages())
    cylinder_liner = route_by_part(routes, "缸套")

    result = calculate_cylinder_liner_allowance(cylinder_liner)

    assert result["warnings"] == []
    inner = result["result"]["inner_finish_to_grind_allowance"]
    outer = result["result"]["outer_finish_to_grind_allowance"]
    assert inner["diameter_allowance"] == 0.8
    assert inner["single_side_allowance"] == 0.4
    assert outer["diameter_allowance"] == 0.8
    assert outer["single_side_allowance"] == 0.4


def test_sqlite_prototype_contains_expected_records(tmp_path: Path):
    routes = merge_routes(load_vlm_pages())
    db_path = tmp_path / "poc.db"

    quality = evaluate_pages(load_vlm_pages(), gold_payloads=[load_p108_gold()])
    build_db(routes, db_path, quality_flags=quality["flags"])

    with sqlite3.connect(db_path) as conn:
        route_count = conn.execute("select count(*) from process_routes").fetchone()[0]
        step_count = conn.execute("select count(*) from process_steps").fetchone()[0]
        dim_count = conn.execute("select count(*) from process_dimensions").fetchone()[0]
        allowance_count = conn.execute("select count(*) from process_allowances").fetchone()[0]
        step_8 = conn.execute(
            """
            select d.upper_deviation, d.lower_deviation, d.source_text
            from process_routes r
            join process_steps s on s.route_id = r.route_id
            join process_dimensions d on d.step_id = s.id
            where r.part_name = '缸套'
              and s.step_no = 8
              and d.surface = 'inner'
              and d.nominal = 279.2
            """
        ).fetchone()
        route_statuses = dict(
            conn.execute("select part_name, quality_status from process_routes").fetchall()
        )

    assert route_count == 3
    assert step_count == 38
    assert dim_count >= 45
    assert allowance_count >= 8
    assert step_8 == (0.05, -0.05, "φ279.2 ±0.05")
    assert route_statuses["输出轴"] == "accepted"
    assert route_statuses["缸套"] == "needs_human_review"
    assert route_statuses["密封件定位套"] == "accepted"


def test_ai_facing_query_api(tmp_path: Path):
    routes = merge_routes(load_vlm_pages())
    quality = evaluate_pages(load_vlm_pages(), gold_payloads=[load_p108_gold()])
    db_path = tmp_path / "poc.db"
    build_db(routes, db_path, quality_flags=quality["flags"])

    output_shaft = get_process_route(db_path, "输出轴")
    cylinder_step_8 = get_step_dimensions(db_path, "缸套", 8)

    assert output_shaft["route"]["step_count"] == 12
    assert [step["step_no"] for step in output_shaft["steps"]] == list(range(1, 13))
    inner = next(
        item
        for item in cylinder_step_8
        if item["surface"] == "inner" and item["nominal"] == 279.2
    )
    assert inner["upper_deviation"] == 0.05
    assert inner["lower_deviation"] == -0.05
    assert inner["source_text"] == "φ279.2 ±0.05"
