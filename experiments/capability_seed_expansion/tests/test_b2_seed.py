"""B2 fixture tests — assert four new candidate families are present and
auditable per the B2 design (design_b2.md)."""

from __future__ import annotations

from experiments.capability_seed_expansion.src.loader import (
    load_candidate_seed,
    load_source_manifest,
)


B2_FAMILIES = (
    "machining_allowance_records",
    "feature_process_records",
    "milling_process_records",
    "drawing_requirement_records",
)


def test_b2_seed_contains_four_target_families():
    seed = load_candidate_seed()
    for family in B2_FAMILIES:
        assert family in seed, f"missing B2 family: {family}"
        assert len(seed[family]) >= 1, f"{family} has no records"


def test_b2_record_count_matches_design_floor():
    seed = load_candidate_seed()
    assert len(seed["machining_allowance_records"]) >= 4
    assert len(seed["feature_process_records"]) >= 1
    assert len(seed["milling_process_records"]) >= 3
    assert len(seed["drawing_requirement_records"]) >= 3


def test_b2_blocking_capability_questions_have_records():
    """Each B2 capability question needs at least one auditable record whose
    subtype the question can route to."""
    seed = load_candidate_seed()

    # MAP-003 expected_subtype: blank_to_finished_diameter_allowance
    map_subtypes = {r["subtype"] for r in seed["machining_allowance_records"]}
    assert any("blank_to_finished" in st for st in map_subtypes), (
        "MAP-003 needs blank_to_finished record"
    )

    # FPS-001 expected_subtype: d_shaped_hole_process_selection
    fps_subtypes = {r["subtype"] for r in seed["feature_process_records"]}
    assert any("d_shaped_hole" in st for st in fps_subtypes), (
        "FPS-001 needs D-shape hole record"
    )

    # FPS-002 expected_subtype: inner_radius_milling_inspection
    mill_subtypes = {r["subtype"] for r in seed["milling_process_records"]}
    assert any("inner_radius" in st for st in mill_subtypes), (
        "FPS-002 needs inner-radius milling record"
    )

    # DRI-002 expected_subtype: weld_surface_requirement
    # DRI-003 expected_subtype: symbol_standard_interpretation
    dr_subtypes = {r["subtype"] for r in seed["drawing_requirement_records"]}
    assert any("weld_surface" in st for st in dr_subtypes), (
        "DRI-002 needs weld_surface_requirement record"
    )
    assert any(
        "symbol_standard_interpretation" in st or "weld_symbol_standard_catalog" in st
        for st in dr_subtypes
    ), "DRI-003 needs welding-symbol interpretation record"


def test_b2_real_drawing_blocking_gaps_have_records():
    """KN-BLANK-ALLOWANCE-001 + KN-MILL-D-SHAPE-001 need records."""
    seed = load_candidate_seed()
    map_records = seed["machining_allowance_records"]
    has_blank_real_example = any(
        r.get("result_json", {}).get("real_drawing_example") for r in map_records
    )
    assert has_blank_real_example, (
        "KN-BLANK-ALLOWANCE-001 needs at least one record citing the real-drawing 103.5→103 example"
    )

    feat_records = seed["feature_process_records"]
    has_d_shape = any(
        "d_shaped" in r["subtype"]
        or "D" in r.get("topic", "")
        for r in feat_records
    )
    assert has_d_shape, "KN-MILL-D-SHAPE-001 needs D-shape feature_process record"


def test_b2_records_carry_payload_field():
    """Every B2 record must have one of result_json / guidance_json /
    method_json (loader already enforces this; this test pins the contract per
    family for B2)."""
    seed = load_candidate_seed()
    for family in B2_FAMILIES:
        for record in seed[family]:
            payload = (
                record.get("result_json")
                or record.get("guidance_json")
                or record.get("method_json")
            )
            assert payload is not None, f"{record['id']} missing payload"


def test_b2_manifest_covers_all_b2_records():
    seed = load_candidate_seed()
    manifest = load_source_manifest()
    manifest_ids = {entry["record_id"] for entry in manifest}
    for family in B2_FAMILIES:
        for record in seed[family]:
            assert record["id"] in manifest_ids, (
                f"B2 record {record['id']} has no manifest entry"
            )


def test_b2_no_record_relies_on_needs_human_review_for_coverage():
    """B2 design forbids needs_human_review from counting toward gap reduction."""
    seed = load_candidate_seed()
    for family in B2_FAMILIES:
        for record in seed[family]:
            assert record["quality_status"] != "needs_human_review", (
                f"{record['id']} is needs_human_review; cannot count toward B2 coverage"
            )


def test_b2_welding_records_cite_gb_t_324():
    seed = load_candidate_seed()
    for record in seed["drawing_requirement_records"]:
        assert "324" in record["source_doc"], (
            f"welding record {record['id']} should cite GB/T 324"
        )


def test_b2_d_shape_record_excludes_lathe():
    """D-shape feature must explicitly exclude lathes (real-drawing constraint)."""
    seed = load_candidate_seed()
    d_shape = next(
        r for r in seed["feature_process_records"]
        if "d_shaped" in r["subtype"]
    )
    incompat = d_shape["result_json"].get("incompatible_equipment", [])
    assert any("车床" in x for x in incompat), (
        "D-shape record must mark lathes as incompatible"
    )
