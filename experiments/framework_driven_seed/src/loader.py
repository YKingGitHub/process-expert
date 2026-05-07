"""Load and validate the framework-driven seed."""

from __future__ import annotations

import json
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = EXPERIMENT_ROOT / "data" / "seed_v1.json"
MANIFEST_PATH = EXPERIMENT_ROOT / "data" / "source_manifest.json"


def load_seed(path: Path = SEED_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def index_by_branch(seed: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for record in seed:
        index.setdefault(record["framework_branch"], []).append(record)
    return index


def index_by_family(seed: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for record in seed:
        index.setdefault(record["family"], []).append(record)
    return index
