"""Load and validate B1 capability seed expansion fixtures."""

from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = EXPERIMENT_ROOT / "data"
CANDIDATE_SEED_PATH = DATA_DIR / "candidate_seed.json"
SOURCE_MANIFEST_PATH = DATA_DIR / "source_manifest.json"

REQUIRED_RECORD_FIELDS = {
    "id",
    "knowledge_type",
    "family",
    "subtype",
    "topic",
    "source_doc",
    "source_page",
    "source_ref",
    "source_text",
    "quality_status",
    "quality_flags",
    "tags",
}

PAYLOAD_FIELDS = {"result_json", "method_json", "guidance_json"}
ALLOWED_QUALITY_STATUSES = {"accepted", "accepted_with_flags", "needs_human_review"}
SOURCE_TEXT_MAX_LEN = 240

REQUIRED_MANIFEST_FIELDS = {
    "record_id",
    "source_kind",
    "source_path_or_doc",
    "source_page",
    "source_ref",
    "evidence_type",
    "copyright_note",
    "review_status",
}


def load_candidate_seed(path: Path = CANDIDATE_SEED_PATH) -> dict[str, list[dict]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_manifest(path: Path = SOURCE_MANIFEST_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_candidate_seed(seed: dict[str, list[dict]]) -> list[str]:
    errors: list[str] = []
    for family, records in seed.items():
        if not isinstance(records, list):
            errors.append(f"{family}: value is not a list")
            continue
        for index, record in enumerate(records):
            errors.extend(_validate_record(record, family, index))
    return errors


def _validate_record(record: dict, family: str, index: int) -> list[str]:
    errors: list[str] = []
    record_id = record.get("id", f"{family}[{index}]")
    missing = REQUIRED_RECORD_FIELDS - set(record)
    for field in sorted(missing):
        errors.append(f"{record_id} missing required field: {field}")

    if not PAYLOAD_FIELDS.intersection(record):
        errors.append(
            f"{record_id} missing one of payload fields: {sorted(PAYLOAD_FIELDS)}"
        )

    status = record.get("quality_status")
    if status is not None and status not in ALLOWED_QUALITY_STATUSES:
        errors.append(
            f"{record_id} quality_status={status!r} not in {sorted(ALLOWED_QUALITY_STATUSES)}"
        )

    source_text = record.get("source_text")
    if isinstance(source_text, str) and len(source_text) > SOURCE_TEXT_MAX_LEN:
        errors.append(
            f"{record_id} source_text length {len(source_text)} exceeds "
            f"{SOURCE_TEXT_MAX_LEN}: paraphrase or split"
        )

    if record.get("family") and record["family"] != family:
        errors.append(
            f"{record_id} family={record['family']!r} does not match container {family!r}"
        )

    if status == "needs_human_review" and not record.get("quality_flags"):
        errors.append(
            f"{record_id} is needs_human_review but quality_flags is empty"
        )

    return errors


def validate_source_manifest(
    manifest: list[dict], seed: dict[str, list[dict]]
) -> list[str]:
    errors: list[str] = []
    seed_ids = {record["id"] for records in seed.values() for record in records}
    manifest_by_id: dict[str, dict] = {}

    for index, entry in enumerate(manifest):
        missing = REQUIRED_MANIFEST_FIELDS - set(entry)
        if missing:
            label = entry.get("record_id", f"manifest[{index}]")
            errors.append(
                f"{label} manifest missing fields: {sorted(missing)}"
            )
        record_id = entry.get("record_id")
        if record_id:
            if record_id in manifest_by_id:
                errors.append(f"{record_id} duplicate manifest entry")
            manifest_by_id[record_id] = entry

    for record_id in sorted(seed_ids):
        if record_id not in manifest_by_id:
            errors.append(f"{record_id} has no source_manifest entry")

    for manifest_id in sorted(manifest_by_id):
        if manifest_id not in seed_ids:
            errors.append(
                f"{manifest_id} appears in manifest but no candidate record"
            )

    return errors
