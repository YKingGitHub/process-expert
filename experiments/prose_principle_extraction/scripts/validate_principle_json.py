#!/usr/bin/env python3
"""Validate prose principle extraction JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.prose_principle_extraction.src.schema import (  # noqa: E402
    validate_principle_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    data = json.loads(args.path.read_text(encoding="utf-8"))
    payload = data.get("payload", data)
    errors = validate_principle_payload(payload)
    print(json.dumps({"path": str(args.path), "error_count": len(errors), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
