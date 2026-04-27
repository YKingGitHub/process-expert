"""Load fixtures for the real drawing planning POC."""

from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = EXPERIMENT_ROOT / "fixtures"
DRAWING_ANALYSIS_PATH = FIXTURE_DIR / "drawing_analysis.json"
EQUIPMENT_BLANK_PATH = FIXTURE_DIR / "equipment_blank.json"
CAD_SUMMARY_PATH = FIXTURE_DIR / "cad_summary.json"
REFERENCE_ROUTE_PATH = FIXTURE_DIR / "reference_route.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_drawing_analysis(path: Path = DRAWING_ANALYSIS_PATH) -> dict:
    return load_json(path)


def load_equipment_blank(path: Path = EQUIPMENT_BLANK_PATH) -> dict:
    return load_json(path)


def load_cad_summary(path: Path = CAD_SUMMARY_PATH) -> dict:
    return load_json(path)


def load_reference_route(path: Path = REFERENCE_ROUTE_PATH) -> dict:
    return load_json(path)
