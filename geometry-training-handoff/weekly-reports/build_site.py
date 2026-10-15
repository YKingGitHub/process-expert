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
ID_PATTERN = re.compile(
    r"20\d{2}-W(?:0[1-9]|[1-4]\d|5[0-3])(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?"
)
LEGACY_DEMO_BUNDLES = (
    Path("geometry-training-handoff/demos/2026-10-15-deepcad-style-preview-3-v1"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bundle_file_is_private(relative: Path) -> bool:
    """Return whether a local-only bundle file must stay out of Pages.

    The demo keeps exact source PDFs, duplicate STEP files, and native-size
    crops locally.  Git ignores them, but a local archive build still sees
    them, so the publisher must apply the same boundary explicitly.
    """

    if "__pycache__" in relative.parts or relative.suffix == ".pyc":
        return True
    if relative.suffix.lower() == ".step":
        return True
    if relative.suffix.lower() == ".pdf" and "source" in relative.parts:
        return True
    return relative.name.endswith("_native.png")


def bundle_files(bundle: Path) -> list[Path]:
    """List public regular files in a bundle in deterministic order."""

    files: list[Path] = []
    for candidate in sorted(bundle.rglob("*")):
        relative = candidate.relative_to(bundle)
        if bundle_file_is_private(relative):
            continue
        if candidate.is_symlink():
            raise ValueError(f"bundle contains a symlink: {relative}")
        if candidate.is_file():
            files.append(candidate)
    return files


def bundle_sha256(bundle: Path) -> str:
    """Hash public bundle paths and bytes so assets are immutable too."""

    digest = hashlib.sha256()
    for path in bundle_files(bundle):
        relative = path.relative_to(bundle).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def copy_bundle(bundle: Path, destination: Path) -> None:
    """Copy only the public, checksummed portion of a report bundle."""

    for source in bundle_files(bundle):
        relative = source.relative_to(bundle)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


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
            f'<div class="week">{html.escape(report["id"])} {newest_badge}</div>'
            f'<h2>{html.escape(report["title"])}</h2>'
            f'<p>{html.escape(report["summary"])}</p>'
            f'<a href="reports/{html.escape(report["id"])}/">打开报告 →</a>'
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
<p class="lead">按 ISO 周永久归档；同周可追加验收报告，不覆盖历史页面。</p>
<a class="latest" href="latest/">打开最新报告 · {html.escape(newest["id"])} →</a>
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

    identifiers: set[str] = set()
    normalized_reports: list[dict[str, str]] = []
    for raw in reports:
        report = {key: str(raw[key]) for key in ("week", "date", "title", "summary", "source", "sha256")}
        if not WEEK_PATTERN.fullmatch(report["week"]):
            raise ValueError(f"invalid ISO week: {report['week']}")
        report["id"] = str(raw.get("id", report["week"]))
        if not ID_PATTERN.fullmatch(report["id"]) or not report["id"].startswith(report["week"]):
            raise ValueError(f"invalid report id: {report['id']}")
        if report["id"] in identifiers:
            raise ValueError(f"duplicate report id: {report['id']}")
        identifiers.add(report["id"])
        source = inside(repo_root, repo_root / report["source"])
        if not source.is_file():
            raise FileNotFoundError(source)
        actual_digest = sha256(source)
        if actual_digest != report["sha256"]:
            raise ValueError(
                f"historical report changed: {report['week']} expected {report['sha256']} got {actual_digest}"
            )
        destination = output / "reports" / report["id"] / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Copy the original source path too, so branch-source Pages and the
        # Actions artifact expose identical durable links. Bundled reports use
        # a relative redirect, keeping all assets in one location.
        original_destination = output / report["source"]
        original_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, original_destination)
        if raw.get("bundle"):
            bundle = inside(repo_root, repo_root / str(raw["bundle"]))
            if not bundle.is_dir() or source.parent != bundle:
                raise ValueError("bundle must be the source report's parent directory")
            report["bundle"] = str(bundle.relative_to(repo_root))
            expected_bundle_digest = str(raw.get("bundle_sha256", ""))
            actual_bundle_digest = bundle_sha256(bundle)
            if not expected_bundle_digest:
                raise ValueError(f"bundle has no checksum: {report['id']}")
            if actual_bundle_digest != expected_bundle_digest:
                raise ValueError(
                    "historical report bundle changed: "
                    f"{report['id']} expected {expected_bundle_digest} got {actual_bundle_digest}"
                )
            report["bundle_sha256"] = expected_bundle_digest
            copy_bundle(bundle, output / report["bundle"])
            target = "../../" + report["source"]
            destination.write_text(
                f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={html.escape(target)}"><a href="{html.escape(target)}">打开验收报告</a>',
                encoding="utf-8",
            )
        else:
            shutil.copy2(source, destination)
        normalized_reports.append(report)

    # Preserve only explicitly named, already-published demos when Pages
    # switches from branch-source serving to the generated Actions artifact.
    # Do not crawl the demos tree: it also contains local/generated material.
    for legacy_relative in LEGACY_DEMO_BUNDLES:
        legacy_bundle = inside(repo_root, repo_root / legacy_relative)
        if not legacy_bundle.is_dir():
            raise FileNotFoundError(f"legacy demo bundle is missing: {legacy_relative}")
        copy_bundle(legacy_bundle, output / legacy_relative)

    normalized_reports.sort(key=lambda report: (report["date"], report["id"]), reverse=True)
    latest_destination = output / "latest" / "index.html"
    latest_destination.parent.mkdir(parents=True, exist_ok=True)
    latest_target = "../reports/" + normalized_reports[0]["id"] + "/"
    latest_destination.write_text(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={html.escape(latest_target)}"><a href="{html.escape(latest_target)}">打开最新报告</a>',
        encoding="utf-8",
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(
        archive_home(str(manifest["site_title"]), normalized_reports), encoding="utf-8"
    )
    (output / ".nojekyll").touch()
    (output / "reports.json").write_text(
        json.dumps({"reports": normalized_reports}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest_destination = output / manifest_path.relative_to(repo_root)
    manifest_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, manifest_destination)
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
