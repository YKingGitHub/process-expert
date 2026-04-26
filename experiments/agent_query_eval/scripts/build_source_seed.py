#!/usr/bin/env python3
"""Build the source-PDF-backed seed used by Sprint B query evaluation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.agent_query_eval.src.data_loader import (  # noqa: E402
    DATA_DIR,
    load_gold_seed,
)
from experiments.agent_query_eval.src.source_seed_builder import (  # noqa: E402
    build_source_replaced_seed,
)


SOURCE_SEED_PATH = DATA_DIR / "source_replaced_seed.json"
SOURCE_REPORT_PATH = DATA_DIR / "source_replacement_report.json"


def main() -> int:
    result = build_source_replaced_seed(load_gold_seed())
    write_json(SOURCE_SEED_PATH, result.seed)
    write_json(SOURCE_REPORT_PATH, result.report)
    print(
        json.dumps(
            {
                "source_seed_path": str(SOURCE_SEED_PATH),
                "source_report_path": str(SOURCE_REPORT_PATH),
                "replaced_count": result.report["replaced_count"],
                "retained_manual_count": result.report["retained_manual_count"],
                "source_quality_status": result.report["source_quality"]["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
