from __future__ import annotations

import json
from pathlib import Path

from experiments.prose_principle_extraction.src.loader import (
    load_principle_records,
    records_by_id,
)
from experiments.prose_principle_extraction.src.quality_gate import evaluate_prose_fixtures
from experiments.prose_principle_extraction.src.schema import validate_principle_payload


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source" / "p107_principles.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]


def test_fixture_satisfies_principle_schema():
    assert validate_principle_payload(load_fixture()) == []


def test_fixture_extracts_keyslot_symmetry_inspection_method():
    payload = load_fixture()
    records = payload["principle_records"]
    keyslot = next(record for record in records if record["id"] == "PR-INSPECTION-KEYSLOT-001")

    assert keyslot["principle_type"] == "inspection_method"
    assert "键槽对称度" in keyslot["topic"]
    assert "偏摆仪" in keyslot["source_text"]
    assert "量块" in keyslot["source_text"]
    assert keyslot["confidence"] >= 0.8


def test_fixture_loader_indexes_records_by_id():
    records = records_by_id()

    assert "PR-INSPECTION-KEYSLOT-001" in records
    assert records["PR-INSPECTION-KEYSLOT-001"]["_source_page"] == 107
    assert records["PR-INSPECTION-KEYSLOT-001"]["_fixture_path"].endswith("p107_principles.json")
    assert len(load_principle_records()) >= 2


def test_prose_quality_gate_accepts_checked_in_fixtures():
    report = evaluate_prose_fixtures()

    assert report["status"] == "accepted"
    assert report["fixture_count"] == 1
    assert report["record_count"] >= 2
    assert report["flag_count"] == 0
