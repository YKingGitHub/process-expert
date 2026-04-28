"""Load fixtures for the knowledge capability baseline."""

from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = EXPERIMENT_ROOT / "data"
QUESTIONS_PATH = DATA_DIR / "capability_questions.json"
REAL_DRAWING_GAP_MAP_PATH = DATA_DIR / "real_drawing_gap_map.json"


def load_capability_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_real_drawing_gap_map(path: Path = REAL_DRAWING_GAP_MAP_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))

