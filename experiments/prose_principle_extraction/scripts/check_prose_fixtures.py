#!/usr/bin/env python3
"""Run quality gates for all checked-in prose principle fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.prose_principle_extraction.src.quality_gate import (  # noqa: E402
    evaluate_prose_fixtures,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=REPO_ROOT / "experiments" / "prose_principle_extraction" / "fixtures" / "source",
    )
    args = parser.parse_args()

    report = evaluate_prose_fixtures(args.fixture_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
