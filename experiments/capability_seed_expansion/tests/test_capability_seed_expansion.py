"""Contract tests for B1 capability seed expansion fixtures and merge."""

from __future__ import annotations

import re

from experiments.agent_query_eval.src.data_loader import load_source_replaced_seed
from experiments.capability_seed_expansion.src.loader import (
    REQUIRED_RECORD_FIELDS,
    load_candidate_seed,
    load_source_manifest,
    validate_candidate_seed,
    validate_source_manifest,
)
from experiments.capability_seed_expansion.src.seed_merge import build_expanded_seed


B1_FAMILIES = (
    "standard_clause_records",
    "inspection_records",
    "equipment_capability_records",
)
ALLOWED_QUALITY_STATUSES = {"accepted", "accepted_with_flags", "needs_human_review"}
SOURCE_TEXT_MAX_LEN = 240


def test_b1_covers_three_target_families():
    candidate = load_candidate_seed()
    for family in B1_FAMILIES:
        assert family in candidate, f"missing family: {family}"
        assert len(candidate[family]) >= 1, f"family {family} has zero records"


def test_every_candidate_record_has_required_fields():
    candidate = load_candidate_seed()
    errors = validate_candidate_seed(candidate)
    assert errors == [], errors


def test_required_record_fields_match_b1_design():
    expected = {
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
    assert expected.issubset(REQUIRED_RECORD_FIELDS)


def test_every_candidate_record_has_one_payload_field():
    candidate = load_candidate_seed()
    for family, records in candidate.items():
        for record in records:
            payload_fields = {"result_json", "method_json", "guidance_json"}
            present = payload_fields.intersection(record.keys())
            assert present, (
                f"{family}/{record.get('id')} missing one of {sorted(payload_fields)}"
            )


def test_candidate_record_quality_status_is_allowed():
    candidate = load_candidate_seed()
    for family, records in candidate.items():
        for record in records:
            assert record["quality_status"] in ALLOWED_QUALITY_STATUSES, (
                f"{record['id']} status not allowed: {record['quality_status']}"
            )


def test_candidate_record_source_text_is_short():
    candidate = load_candidate_seed()
    for family, records in candidate.items():
        for record in records:
            assert len(record["source_text"]) <= SOURCE_TEXT_MAX_LEN, (
                f"{record['id']} source_text exceeds {SOURCE_TEXT_MAX_LEN} chars"
            )


def test_candidate_record_id_format_is_stable():
    candidate = load_candidate_seed()
    pattern = re.compile(r"^[A-Z][A-Z0-9-]{2,79}$")
    for records in candidate.values():
        for record in records:
            assert pattern.match(record["id"]), f"bad id: {record['id']}"


def test_candidate_record_family_field_matches_container():
    candidate = load_candidate_seed()
    for family, records in candidate.items():
        for record in records:
            assert record["family"] == family, (
                f"{record['id']} family={record['family']} but in {family}"
            )


def test_source_manifest_covers_every_record():
    candidate = load_candidate_seed()
    manifest = load_source_manifest()
    errors = validate_source_manifest(manifest, candidate)
    assert errors == [], errors


def test_loader_rejects_record_missing_source_metadata():
    bad_seed = {
        "standard_clause_records": [
            {
                "id": "STD-BAD-001",
                "knowledge_type": "standard_clause",
                "family": "standard_clause_records",
                "subtype": "general_tolerance_linear_m",
                "topic": "x",
                "quality_status": "accepted",
                "quality_flags": [],
                "tags": [],
                "result_json": {},
            }
        ]
    }
    errors = validate_candidate_seed(bad_seed)
    assert any("source_doc" in err or "source_page" in err for err in errors), errors


def test_loader_rejects_long_verbatim_clause():
    long_text = "甲" * (SOURCE_TEXT_MAX_LEN + 1)
    bad_seed = {
        "standard_clause_records": [
            {
                "id": "STD-LONG-001",
                "knowledge_type": "standard_clause",
                "family": "standard_clause_records",
                "subtype": "x",
                "topic": "x",
                "source_doc": "x.pdf",
                "source_page": 1,
                "source_ref": "x",
                "source_text": long_text,
                "quality_status": "accepted",
                "quality_flags": [],
                "tags": [],
                "result_json": {},
            }
        ]
    }
    errors = validate_candidate_seed(bad_seed)
    assert any("source_text" in err for err in errors), errors


def test_seed_merge_preserves_all_base_records():
    base = load_source_replaced_seed()
    candidate = load_candidate_seed()
    expanded = build_expanded_seed(base, candidate)

    for family, records in base.items():
        merged_ids = {record["id"] for record in expanded[family]}
        for record in records:
            assert record["id"] in merged_ids, (
                f"base record {record['id']} dropped in merge"
            )


def test_seed_merge_adds_candidate_records_under_correct_family():
    base = load_source_replaced_seed()
    candidate = load_candidate_seed()
    expanded = build_expanded_seed(base, candidate)

    for family in B1_FAMILIES:
        assert family in expanded
        merged_ids = {record["id"] for record in expanded[family]}
        for record in candidate[family]:
            assert record["id"] in merged_ids


def test_seed_merge_returns_new_dict_without_mutating_inputs():
    base = load_source_replaced_seed()
    candidate = load_candidate_seed()
    base_ids_before = {fam: {r["id"] for r in rs} for fam, rs in base.items()}

    build_expanded_seed(base, candidate)

    base_ids_after = {fam: {r["id"] for r in rs} for fam, rs in base.items()}
    assert base_ids_before == base_ids_after


def test_b1_blocking_real_drawing_gaps_have_records():
    """B1 must contain at least one record per blocking real-drawing gap."""
    candidate = load_candidate_seed()

    standard_subtypes = {r["subtype"] for r in candidate["standard_clause_records"]}
    assert any("general_tolerance" in st for st in standard_subtypes), (
        "missing GB/T 1804-m general tolerance record for KN-GENERAL-TOL-001"
    )

    inspection_subtypes = {r["subtype"] for r in candidate["inspection_records"]}
    assert any(
        "position" in st or "datum" in st or "symmetry" in st
        for st in inspection_subtypes
    ), "missing position/datum-based inspection record for KN-GTOL-POSITION-001"

    equipment_topics = {r["topic"] for r in candidate["equipment_capability_records"]}
    assert any(
        "数控" in topic or "加工中心" in topic or "车床" in topic
        for topic in equipment_topics
    ), "missing equipment record for KN-EQUIPMENT-001 (数控车床/加工中心/车床)"


def test_needs_human_review_flag_is_visible_when_used():
    candidate = load_candidate_seed()
    for records in candidate.values():
        for record in records:
            if record["quality_status"] == "needs_human_review":
                assert record["quality_flags"], (
                    f"{record['id']} is needs_human_review but no quality_flags listed"
                )
