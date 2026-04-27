from __future__ import annotations

import json
from pathlib import Path

from experiments.vlm_source_pdf_process_cards.src.compare import (
    find_known_p108_poc_mismatches,
)
from experiments.vlm_source_pdf_process_cards.src.schema import (
    validate_process_card_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = EXPERIMENT_ROOT / "fixtures" / "gold" / "p108_cylinder_liner.json"
POC_FIXTURE_PATH = (
    REPO_ROOT
    / "experiments"
    / "process_calc_extracted_content"
    / "fixtures"
    / "process_cards_sample.json"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_manual_gold_satisfies_vlm_schema_contract():
    payload = load_json(GOLD_PATH)

    assert validate_process_card_payload(payload) == []


def test_manual_gold_preserves_symmetric_tolerance_from_source_pdf():
    payload = load_json(GOLD_PATH)
    step_8 = payload["cards"][0]["steps"][7]
    inner = step_8["dimensions"][0]
    outer = step_8["dimensions"][1]

    assert inner["source_text"] == "φ279.2±0.05mm"
    assert inner["upper_deviation"] == 0.05
    assert inner["lower_deviation"] == -0.05
    assert outer["source_text"] == "φ300.8±0.05mm"
    assert outer["upper_deviation"] == 0.05
    assert outer["lower_deviation"] == -0.05


def test_old_poc_fixture_loses_symmetric_tolerance_on_p108():
    gold = load_json(GOLD_PATH)
    poc = load_json(POC_FIXTURE_PATH)

    mismatches = find_known_p108_poc_mismatches(gold, poc)

    assert len(mismatches) == 4
    assert {item["step_no"] for item in mismatches} == {8, 9}
    assert all(item["code"] == "symmetric_tolerance_lost" for item in mismatches)
