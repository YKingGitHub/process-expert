"""KB-lookup tests against framework_seed.db.

These tests assume ``experiments/framework_driven_seed/sqlite/ingest.py``
has been run at least once (the DB lives in the repo). If the DB is
missing they skip rather than fail, so a clean clone can still run other
process_calc tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from process_calc import calculate
from process_calc.errors import MissingParameterError
from process_calc.lookup_kb import _DEFAULT_DB


pytestmark = pytest.mark.skipif(
    not _DEFAULT_DB.exists(),
    reason=f"KB DB not present at {_DEFAULT_DB}; run ingest.py to materialize.",
)


def test_path_precision_outer_cylinder_finish_turn():
    """粗车→半精车→精车 (或磨) on outer cylinder: textbook IT 7-8, Ra 1.6-6.3.

    Source: STD-2.3.2-OUTER-CYL-PATH-001 row 3.
    """
    r = calculate("lookup_path_precision", path_keyword="粗车→半精车→精车 (或磨)")
    matches = r["result"]["matches"]
    assert any(
        m["it"] == "7-8" and m["ra_min"] == 1.6 and m["ra_max"] == 6.3
        for m in matches
    )
    assert r["verified"] is True
    assert r["unit"] == "IT/Ra"


def test_economic_precision_method_filter_returns_rows():
    """method='镗' should hit multiple §2.8.1.4 economic-precision rows."""
    r = calculate("lookup_economic_precision", method="镗")
    payload = r["result"]
    assert payload["match_count"] >= 5
    for row in payload["matches"]:
        assert "镗" in (row["method"] or "")
        assert row["it"] is not None


def test_economic_precision_requires_filter():
    """No method or feature → MissingParameterError."""
    with pytest.raises(MissingParameterError):
        calculate("lookup_economic_precision")


def test_method_position_error_textbook_values():
    """孔轴线到基准面 — best is 坐标镗床 at 0.02~0.04 mm.

    Source: STD-2.3.2-METHOD-ERRORS-001 (机械加工方法可达定位精度对照).
    """
    r = calculate(
        "lookup_method_position_error",
        feature="孔轴线到基准面",
    )
    matches = r["result"]["matches"]
    assert matches, "expected at least one match"
    best = matches[0]  # ordered ASC by error_mm_min
    assert best["error_mm_min"] == pytest.approx(0.02)
    assert best["error_mm_max"] == pytest.approx(0.04)
    assert "坐标镗床" in best["method"]
    assert r["unit"] == "mm"


def test_method_position_error_requires_feature():
    with pytest.raises(MissingParameterError):
        calculate("lookup_method_position_error", feature="")


def test_lookup_methods_registered_in_method_registry():
    from process_calc import METHOD_REGISTRY

    assert "lookup_economic_precision" in METHOD_REGISTRY
    assert "lookup_path_precision" in METHOD_REGISTRY
    assert "lookup_method_position_error" in METHOD_REGISTRY


def test_kb_db_resolution_via_env(tmp_path, monkeypatch):
    """If PROCESS_CALC_KB_DB points to a non-existent path, lookup raises."""
    monkeypatch.setenv("PROCESS_CALC_KB_DB", str(tmp_path / "nope.db"))
    from process_calc.errors import InputOutOfRangeError

    with pytest.raises(InputOutOfRangeError):
        calculate("lookup_path_precision", path_keyword="粗车")
