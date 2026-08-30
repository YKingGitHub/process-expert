"""Quality gates for prose principle extraction fixtures."""

from __future__ import annotations

from pathlib import Path

from .loader import FIXTURE_DIR, load_principle_payloads
from .schema import validate_principle_payload


MIN_CONFIDENCE = 0.8


def evaluate_prose_fixtures(fixture_dir: Path = FIXTURE_DIR) -> dict:
    payloads = load_principle_payloads(fixture_dir)
    flags: list[dict] = []
    seen_ids: dict[str, str] = {}
    record_count = 0

    for payload in payloads:
        fixture_path = payload.get("_fixture_path", "")
        schema_errors = validate_principle_payload(payload)
        for error in schema_errors:
            flags.append(
                {
                    "code": "schema_error",
                    "fixture_path": fixture_path,
                    "error": error,
                }
            )

        for record in payload.get("principle_records", []):
            record_count += 1
            record_id = record.get("id")
            if record_id in seen_ids:
                flags.append(
                    {
                        "code": "duplicate_record_id",
                        "id": record_id,
                        "first_fixture": seen_ids[record_id],
                        "fixture_path": fixture_path,
                    }
                )
            else:
                seen_ids[record_id] = fixture_path

            if record.get("confidence", 0) < MIN_CONFIDENCE:
                flags.append(
                    {
                        "code": "low_confidence",
                        "id": record_id,
                        "fixture_path": fixture_path,
                        "confidence": record.get("confidence"),
                    }
                )
            if not has_chinese_evidence(record.get("source_text", "")):
                flags.append(
                    {
                        "code": "weak_source_text",
                        "id": record_id,
                        "fixture_path": fixture_path,
                    }
                )
            if "表格" in str(record.get("evidence_region", "")):
                flags.append(
                    {
                        "code": "possible_table_evidence",
                        "id": record_id,
                        "fixture_path": fixture_path,
                        "evidence_region": record.get("evidence_region"),
                    }
                )

    blocking_codes = {"schema_error", "duplicate_record_id", "low_confidence", "weak_source_text"}
    status = "accepted" if not any(flag["code"] in blocking_codes for flag in flags) else "needs_review"
    return {
        "fixture_count": len(payloads),
        "record_count": record_count,
        "flag_count": len(flags),
        "flags": flags,
        "status": status,
    }


def has_chinese_evidence(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)
