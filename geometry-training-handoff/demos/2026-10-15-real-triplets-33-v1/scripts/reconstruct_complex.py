#!/usr/bin/env python3
"""Materialize the five complex editable reconstructions and their references."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


CASE_IDS = tuple(f"case_{index:03d}" for index in range(1, 6))
DEFAULT_SOURCE = Path(
    "/hpc2hdd/home/lwang592/projects/.cache/process-expert/"
    "drawing_20260810_single/cases"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--base", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()

    for case_id in CASE_IDS:
        case_dir = args.base / "cases" / case_id
        source_step = args.source / case_id / "ground_truth" / "ground_truth.step"
        reference_step = case_dir / "reference.step"
        model_path = case_dir / "model.py"
        authoring_path = case_dir / "authoring.json"

        for required in (source_step, model_path, authoring_path):
            if not required.is_file():
                raise FileNotFoundError(required)

        shutil.copyfile(source_step, reference_step)
        reference_step.chmod(0o444)
        subprocess.run([sys.executable, "model.py"], cwd=case_dir, check=True)
        print(f"ready: {case_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
