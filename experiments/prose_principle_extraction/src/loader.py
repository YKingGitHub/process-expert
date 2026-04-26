"""Load checked-in prose principle extraction fixtures."""

from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = EXPERIMENT_ROOT / "fixtures" / "source"


def load_principle_payloads(fixture_dir: Path = FIXTURE_DIR) -> list[dict]:
    payloads = []
    for path in sorted(fixture_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = data.get("payload", data)
        payload["_fixture_path"] = str(path)
        payloads.append(payload)
    return payloads


def load_principle_records(fixture_dir: Path = FIXTURE_DIR) -> list[dict]:
    records = []
    for payload in load_principle_payloads(fixture_dir):
        source_page = payload.get("source_page")
        fixture_path = payload.get("_fixture_path")
        for record in payload.get("principle_records", []):
            item = dict(record)
            item["_source_page"] = source_page
            item["_fixture_path"] = fixture_path
            records.append(item)
    return records


def records_by_id(fixture_dir: Path = FIXTURE_DIR) -> dict[str, dict]:
    result = {}
    for record in load_principle_records(fixture_dir):
        record_id = record["id"]
        if record_id in result:
            raise ValueError(f"Duplicate prose principle id: {record_id}")
        result[record_id] = record
    return result
