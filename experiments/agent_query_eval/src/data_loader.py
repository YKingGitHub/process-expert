"""Load agent query evaluation fixtures."""

from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = EXPERIMENT_ROOT / "data"
QUESTIONS_PATH = DATA_DIR / "questions.json"
GOLD_SEED_PATH = DATA_DIR / "gold_seed.json"


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gold_seed(path: Path = GOLD_SEED_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
