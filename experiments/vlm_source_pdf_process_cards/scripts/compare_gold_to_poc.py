#!/usr/bin/env python3
"""Compare source-PDF gold JSON with the previous POC process-card fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.vlm_source_pdf_process_cards.src.compare import (
    find_known_p108_poc_mismatches,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = EXPERIMENT_ROOT / "fixtures" / "gold" / "p108_cylinder_liner.json"
DEFAULT_POC = (
    REPO_ROOT
    / "experiments"
    / "process_calc_extracted_content"
    / "fixtures"
    / "process_cards_sample.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--poc", type=Path, default=DEFAULT_POC)
    args = parser.parse_args()

    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    poc = json.loads(args.poc.read_text(encoding="utf-8"))
    mismatches = find_known_p108_poc_mismatches(gold, poc)
    result = {
        "gold": str(args.gold),
        "poc": str(args.poc),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
