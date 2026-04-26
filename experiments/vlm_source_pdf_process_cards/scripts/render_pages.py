#!/usr/bin/env python3
"""Render selected source PDF pages to PNG images for VLM extraction."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


DEFAULT_PDF = Path("references/工艺知识库.pdf")
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = EXPERIMENT_ROOT / "fixtures" / "page_images"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pages", type=int, nargs="+", default=[106, 107, 108, 109, 110])
    parser.add_argument("--resolution", type=int, default=220)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    args.out.mkdir(parents=True, exist_ok=True)
    for page in args.pages:
        prefix = args.out / f"page_{page}"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                str(args.resolution),
                "-png",
                str(args.pdf),
                str(prefix),
            ],
            check=True,
        )
        generated = args.out / f"page_{page}-{page}.png"
        target = args.out / f"page_{page}.png"
        if generated.exists():
            generated.replace(target)
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
