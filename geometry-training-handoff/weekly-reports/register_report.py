#!/usr/bin/env python3
"""Register one new immutable weekly report in reports.json."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from build_site import WEEK_PATTERN, inside, sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("reports.json"))
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--week", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()

    if not WEEK_PATTERN.fullmatch(args.week):
        parser.error("--week must use ISO format YYYY-Www")
    date.fromisoformat(args.date)
    repo_root = (args.repo_root or Path(__file__).resolve().parents[2]).resolve()
    manifest_path = args.manifest.resolve()
    source = inside(repo_root, repo_root / args.source)
    if not source.is_file():
        raise FileNotFoundError(source)
    source_relative = str(source.relative_to(repo_root))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports = manifest.setdefault("reports", [])
    if any(str(report.get("week")) == args.week for report in reports):
        parser.error(f"week is already registered and will not be overwritten: {args.week}")
    reports.append(
        {
            "week": args.week,
            "date": args.date,
            "title": args.title,
            "summary": args.summary,
            "source": source_relative,
            "sha256": sha256(source),
        }
    )
    reports.sort(key=lambda report: str(report["week"]))
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    print(f"registered {args.week}: {source_relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
