from __future__ import annotations

from experiments.process_calc_extracted_content.src.operation_parser import (
    parse_operation_content,
)


def test_parse_diameters_and_symmetric_tolerance():
    parsed = parse_operation_content("车内径至尺寸 φ270 ±1 mm，车外圆至尺寸 φ310 ±1 mm")

    inner, outer = parsed["diameters"]
    assert inner["value"] == 270
    assert inner["surface"] == "inner"
    assert inner["upper_deviation"] == 1
    assert inner["lower_deviation"] == -1
    assert outer["value"] == 310
    assert outer["surface"] == "outer"


def test_parse_signed_pair_and_single_positive_deviation():
    parsed = parse_operation_content(
        "车内径至 φ279.2 +0.05 mm；磨外圆至图样尺寸 φ300 +0.08/+0.04 mm"
    )

    inner, outer = parsed["diameters"]
    assert inner["value"] == 279.2
    assert inner["upper_deviation"] == 0.05
    assert inner["lower_deviation"] == 0
    assert outer["value"] == 300
    assert outer["upper_deviation"] == 0.08
    assert outer["lower_deviation"] == 0.04


def test_parse_explicit_allowance_and_range():
    parsed = parse_operation_content("铣平面，留加工余量 5 ~ 6mm；另留磨量 0.8mm")

    allowances = parsed["allowances"]
    assert allowances[0]["value"] == 5
    assert allowances[0]["max_value"] == 6
    assert allowances[1]["value"] == 0.8


def test_parse_total_lengths():
    parsed = parse_operation_content("车端面保证尺寸总长 508mm，磨端面保证工件总长 500.4mm")

    assert [item["value"] for item in parsed["lengths"]] == [508, 500.4]
