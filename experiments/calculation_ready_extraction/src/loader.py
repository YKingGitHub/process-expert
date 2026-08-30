"""Load VLM process-card outputs and gold fixtures."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
VLM_OUTPUT_DIR = REPO_ROOT / "experiments" / "vlm_source_pdf_process_cards" / "output"
VLM_FIXTURE_DIR = (
    REPO_ROOT
    / "experiments"
    / "vlm_source_pdf_process_cards"
    / "fixtures"
    / "vlm_outputs"
)
P108_GOLD_PATH = (
    REPO_ROOT
    / "experiments"
    / "vlm_source_pdf_process_cards"
    / "fixtures"
    / "gold"
    / "p108_cylinder_liner.json"
)


def load_vlm_pages(output_dir: Path | None = None) -> list[dict]:
    source_dir = output_dir or default_vlm_dir()
    pages = []
    for path in sorted(source_dir.glob("vlm_page_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = data["payload"]
        payload["_validation_errors"] = data.get("validation_errors", [])
        payload["_fixture_path"] = str(path)
        pages.append(payload)
    return pages


def default_vlm_dir() -> Path:
    if any(VLM_OUTPUT_DIR.glob("vlm_page_*.json")):
        return VLM_OUTPUT_DIR
    return VLM_FIXTURE_DIR


def load_p108_gold(path: Path = P108_GOLD_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
