#!/usr/bin/env python3
"""Build an immutable weekly-report archive for GitHub Pages."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path


WEEK_PATTERN = re.compile(r"20\d{2}-W(?:0[1-9]|[1-4]\d|5[0-3])")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"report source escapes repository: {candidate}") from exc
    return resolved


def archive_home(site_title: str, reports: list[dict[str, str]]) -> str:
    newest = reports[0]
    cards = []
    for index, report in enumerate(reports):
        newest_badge = '<span class="badge">最新</span>' if index == 0 else ""
        cards.append(
            '<article class="report">'
            f'<div class="week">{html.escape(report["week"])} {newest_badge}</div>'
            f'<h2>{html.escape(report["title"])}</h2>'
            f'<p>{html.escape(report["summary"])}</p>'
            f'<a href="reports/{html.escape(report["week"])}/">打开周报 →</a>'
            f'<small>{html.escape(report["date"])}</small>'
            '</article>'
        )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(site_title)}</title>
<style>
:root{{--ink:#172033;--muted:#667085;--line:#d9dee8;--blue:#2457a6;--panel:#f7f9fc}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Segoe UI","PingFang SC",sans-serif}}
main{{width:min(920px,calc(100% - 40px));margin:auto;padding:54px 0 80px}}h1{{font-size:36px;margin:0 0 8px}}.lead{{font-size:18px;color:var(--muted);margin-bottom:28px}}
.latest{{display:inline-block;margin:4px 0 34px;padding:11px 18px;border-radius:7px;color:white;background:var(--blue);text-decoration:none}}
.list{{display:grid;gap:12px}}.report{{padding:20px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}}
.report h2{{font-size:20px;margin:5px 0}}.report p{{margin:6px 0 12px;color:var(--muted)}}.report a{{color:var(--blue);font-weight:650;text-decoration:none}}.report small{{float:right;color:var(--muted)}}
.week{{font:13px ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--muted)}}.badge{{margin-left:7px;padding:2px 7px;border-radius:999px;color:var(--blue);background:#e8f0fc;font:12px system-ui}}
.foot{{margin-top:30px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}}
</style></head><body><main>
<h1>{html.escape(site_title)}</h1>
<p class="lead">每周报告按 ISO 周永久归档；发布新一周不会覆盖旧页面。</p>
<a class="latest" href="latest/">打开最新周报 · {html.escape(newest["week"])} →</a>
<div class="list">{''.join(cards)}</div>
<div class="foot">由 GitHub Actions 自动构建和发布。每个归档源文件都经过 SHA-256 校验，防止历史周报被无意改写。</div>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    repo_root = (args.repo_root or Path(__file__).resolve().parents[2]).resolve()
    output = args.output.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports = manifest.get("reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("manifest contains no reports")

    weeks: set[str] = set()
    normalized_reports: list[dict[str, str]] = []
    for raw in reports:
        report = {key: str(raw[key]) for key in ("week", "date", "title", "summary", "source", "sha256")}
        if not WEEK_PATTERN.fullmatch(report["week"]):
            raise ValueError(f"invalid ISO week: {report['week']}")
        if report["week"] in weeks:
            raise ValueError(f"duplicate week: {report['week']}")
        weeks.add(report["week"])
        source = inside(repo_root, repo_root / report["source"])
        if not source.is_file():
            raise FileNotFoundError(source)
        actual_digest = sha256(source)
        if actual_digest != report["sha256"]:
            raise ValueError(
                f"historical report changed: {report['week']} expected {report['sha256']} got {actual_digest}"
            )
        destination = output / "reports" / report["week"] / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        normalized_reports.append(report)

    normalized_reports.sort(key=lambda report: report["week"], reverse=True)
    latest_source = output / "reports" / normalized_reports[0]["week"] / "index.html"
    latest_destination = output / "latest" / "index.html"
    latest_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(latest_source, latest_destination)
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(
        archive_home(str(manifest["site_title"]), normalized_reports), encoding="utf-8"
    )
    (output / ".nojekyll").touch()
    (output / "reports.json").write_text(
        json.dumps({"reports": normalized_reports}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "report_count": len(normalized_reports),
                "latest": normalized_reports[0]["week"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
