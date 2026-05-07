"""Contract tests for framework-driven seed (pilot)."""

from __future__ import annotations

from collections import Counter

from experiments.framework_driven_seed.src.loader import (
    index_by_branch,
    index_by_family,
    load_manifest,
    load_seed,
)
from experiments.framework_driven_seed.src.schema import (
    FAMILIES,
    PREFIX_BY_FAMILY,
    validate_seed,
)


# Phase 2 pilot scope (per WO-003): tables 4-1, 4-2, 4-3, 4-19, 4-31, 4-32, 4-33.
EXPECTED_BRANCHES = {
    "2.8.1.1",  # 表4-1 影响尺寸精度
    "2.8.1.2",  # 表4-2 影响形状精度
    "2.8.1.3",  # 表4-3 影响位置精度
    "2.4.4",    # 表4-19 米制螺纹经济精度
    "2.8.2.1",  # 表4-31 可达 Ra
    "2.8.2.2",  # 表4-32, 4-33 影响 Ra 因素
}


def test_seed_passes_schema_validation():
    seed = load_seed()
    errors = validate_seed(seed)
    assert errors == [], "\n".join(errors)


def test_seed_covers_all_expected_branches():
    seed = load_seed()
    branches = set(r["framework_branch"] for r in seed)
    assert EXPECTED_BRANCHES.issubset(branches), (
        f"missing expected branches: {EXPECTED_BRANCHES - branches}"
    )


def test_seed_minimum_record_count():
    """WO-003 design floor: ~50 records, with a B4-holdout-relevant subset
    in each family. Pilot extracted 44 records; floor is 40 to leave a
    little wiggle room without being trivially passable."""
    seed = load_seed()
    assert len(seed) >= 40


def test_family_distribution_includes_experience_and_standard():
    seed = load_seed()
    by_family = index_by_family(seed)
    assert "经验" in by_family
    assert "标准" in by_family
    assert len(by_family["经验"]) >= 20  # 23 from tables 4-1/2/3 + 8 from 4-32/33
    assert len(by_family["标准"]) >= 10  # 12 from 4-31 + 1 from 4-19


def test_all_records_have_distinct_ids():
    seed = load_seed()
    counts = Counter(r["id"] for r in seed)
    duplicates = [rid for rid, c in counts.items() if c > 1]
    assert duplicates == [], f"duplicate ids: {duplicates}"


def test_id_prefix_matches_family():
    seed = load_seed()
    for record in seed:
        expected_prefix = PREFIX_BY_FAMILY[record["family"]]
        assert record["id"].startswith(expected_prefix + "-"), (
            f"{record['id']} does not match family prefix {expected_prefix}"
        )


def test_every_record_has_short_source_text():
    seed = load_seed()
    for record in seed:
        assert len(record["source_text"]) <= 240, (
            f"{record['id']} source_text > 240 chars"
        )


def test_thread_record_present_for_b4_holdout():
    """KN-THREAD (B4 holdout gap): 米制螺纹加工 should be answerable."""
    seed = load_seed()
    by_branch = index_by_branch(seed)
    thread_records = by_branch.get("2.4.4", [])
    assert thread_records, "no record for branch 2.4.4 (米制螺纹)"
    record = thread_records[0]
    assert record["family"] == "标准"
    assert "value_table" in record["payload"]
    assert any(row["method"] == "车削" for row in record["payload"]["value_table"])


def test_position_precision_records_present_for_b4_holdout():
    """KN-PERP / KN-RUNOUT / KN-POSITION (B4 holdout gaps) must have
    records explaining factor → impact → improvement_actions."""
    seed = load_seed()
    by_branch = index_by_branch(seed)
    pos_records = by_branch.get("2.8.1.3", [])
    assert len(pos_records) >= 5, (
        f"expected 5+ records under 2.8.1.3 影响位置精度, got {len(pos_records)}"
    )
    for record in pos_records:
        payload = record["payload"]
        assert payload["factor"]
        assert payload["impact"]
        assert isinstance(payload["improvement_actions"], list)
        assert payload["improvement_actions"]


def test_ra_records_cover_methods_used_in_real_drawings():
    """The two test drawings use Ra1.6, Ra3.2, Ra3.2 turning. Make sure
    the seed has 车外圆 + 端铣 entries that bracket these."""
    seed = load_seed()
    ra_records = [r for r in seed if r["framework_branch"] == "2.8.2.1"]
    methods = set()
    for record in ra_records:
        for row in record["payload"].get("value_table", []):
            methods.add(record["topic"])
    assert any("外圆" in t for t in methods), "no 车外圆 record"
    assert any("端铣" in t or "端面" in t for t in methods), "no end-face record"


def test_manifest_covers_all_extracted_tables():
    manifest = load_manifest()
    seed = load_seed()
    seed_branches = set(r["framework_branch"] for r in seed)
    manifest_branches = set(entry["framework_branch"] for entry in manifest)
    assert seed_branches.issubset(manifest_branches), (
        f"manifest missing branches: {seed_branches - manifest_branches}"
    )


def test_no_record_relies_on_needs_human_review():
    """Phase 2 pilot must not count needs_human_review records as covered."""
    seed = load_seed()
    flagged = [r for r in seed if r["quality_status"] == "needs_human_review"]
    assert flagged == [], (
        f"needs_human_review records exist: {[r['id'] for r in flagged]}"
    )
