from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_SCRIPT = SCRIPT_DIR / "build_site.py"
REGISTER_SCRIPT = SCRIPT_DIR / "register_report.py"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WeeklyReportPublishingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.manifest = self.repo / "geometry-training-handoff/weekly-reports/reports.json"
        self.old_source = (
            self.repo
            / "geometry-training-handoff/weekly-reports/2026-W42/index.html"
        )
        self.write(self.old_source, "<!doctype html><title>old three-case report</title>")
        self.write_manifest(
            [
                {
                    "week": "2026-W42",
                    "date": "2026-10-14",
                    "title": "Existing three-case report",
                    "summary": "Must remain immutable and reachable.",
                    "source": str(self.old_source.relative_to(self.repo)),
                    "sha256": file_sha256(self.old_source),
                }
            ]
        )
        self.legacy_demo = (
            self.repo
            / "geometry-training-handoff/demos/2026-10-15-deepcad-style-preview-3-v1"
        )
        self.write(self.legacy_demo / "index.html", "<!doctype html><title>old demo</title>")
        self.write(self.legacy_demo / "render_preview.py", "print('legacy demo')")
        self.write(self.legacy_demo / "assets/case-005-original.webp", b"original")
        self.write(self.legacy_demo / "assets/case-005-normalized.png", b"normalized")
        self.write(self.legacy_demo / "assets/case-005-physical_mm.png", b"physical")
        self.write(self.legacy_demo / "assets/case-005.json", "{}")
        self.write(self.legacy_demo / "local/reference.step", b"private-step")
        self.write(self.legacy_demo / "__pycache__/render_preview.pyc", b"pyc")

        # A generated demo that is not explicitly whitelisted must not leak
        # into the Pages artifact.
        self.unlisted_demo = self.repo / "geometry-training-handoff/demos/unlisted"
        self.write(self.unlisted_demo / "index.html", "must not be published")

    @staticmethod
    def write(path: Path, content: str | bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def write_manifest(self, reports: list[dict[str, str]]) -> None:
        self.write(
            self.manifest,
            json.dumps(
                {"schema_version": 1, "site_title": "Test reports", "reports": reports},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )

    def make_bundle(self) -> Path:
        bundle = (
            self.repo
            / "geometry-training-handoff/demos/2026-10-15-real-triplets-33-v1"
        )
        self.write(bundle / "index.html", "<!doctype html><title>33 triplets</title>")
        self.write(bundle / "app.js", "window.reportReady = true;")
        self.write(bundle / "style.css", "body { color: black; }")
        self.write(bundle / "cases/case_001/structured_views.webp", b"webp-preview")
        self.write(bundle / "cases/case_001/source/page_01.webp", b"webp-source")
        self.write(bundle / "downloads/case_001_triplet.zip", b"zip-bundle")

        # These files exist in a developer's local working tree but are
        # deliberately ignored and must never enter the Pages artifact.
        self.write(bundle / "cases/case_001/source/page_01.pdf", b"private-pdf")
        self.write(bundle / "cases/case_001/reference.step", b"duplicate-step")
        self.write(bundle / "cases/case_001/views/view_01_native.png", b"native-png")
        self.write(bundle / "scripts/__pycache__/helper.cpython-312.pyc", b"pyc")
        return bundle

    def register_bundle(self, bundle: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(REGISTER_SCRIPT),
                "--manifest",
                str(self.manifest),
                "--repo-root",
                str(self.repo),
                "--week",
                "2026-W42",
                "--id",
                "2026-W42-triplets-33",
                "--date",
                "2026-10-15",
                "--title",
                "33 real-drawing triplets",
                "--summary",
                "A same-week validation supplement.",
                "--source",
                str((bundle / "index.html").relative_to(self.repo)),
                "--bundle",
                str(bundle.relative_to(self.repo)),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def build(self, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--manifest",
                str(self.manifest),
                "--repo-root",
                str(self.repo),
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_same_week_supplement_is_allowed_but_duplicate_id_is_rejected(self) -> None:
        bundle = self.make_bundle()

        first = self.register_bundle(bundle)
        self.assertEqual(first.returncode, 0, first.stderr)
        manifest_after_first = self.manifest.read_text(encoding="utf-8")
        reports = json.loads(manifest_after_first)["reports"]
        self.assertEqual(len(reports), 2)
        supplement = next(report for report in reports if report.get("id"))
        self.assertEqual(supplement["week"], "2026-W42")
        self.assertEqual(supplement["id"], "2026-W42-triplets-33")
        self.assertRegex(supplement["bundle_sha256"], r"^[0-9a-f]{64}$")

        duplicate = self.register_bundle(bundle)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("already registered", duplicate.stderr)
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), manifest_after_first)

    def test_build_preserves_old_routes_and_copies_only_public_bundle_assets(self) -> None:
        bundle = self.make_bundle()
        registered = self.register_bundle(bundle)
        self.assertEqual(registered.returncode, 0, registered.stderr)

        output = self.repo / "_site"
        built = self.build(output)
        self.assertEqual(built.returncode, 0, built.stderr)

        old_canonical = output / "reports/2026-W42/index.html"
        old_original = output / self.old_source.relative_to(self.repo)
        self.assertEqual(old_canonical.read_bytes(), self.old_source.read_bytes())
        self.assertEqual(old_original.read_bytes(), self.old_source.read_bytes())

        supplement_entry = output / "reports/2026-W42-triplets-33/index.html"
        self.assertIn(
            "../../geometry-training-handoff/demos/2026-10-15-real-triplets-33-v1/index.html",
            supplement_entry.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "../reports/2026-W42-triplets-33/",
            (output / "latest/index.html").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "reports/2026-W42-triplets-33/",
            (output / "index.html").read_text(encoding="utf-8"),
        )

        published_bundle = output / bundle.relative_to(self.repo)
        for relative in (
            "index.html",
            "app.js",
            "style.css",
            "cases/case_001/structured_views.webp",
            "cases/case_001/source/page_01.webp",
            "downloads/case_001_triplet.zip",
        ):
            self.assertTrue((published_bundle / relative).is_file(), relative)
        for relative in (
            "cases/case_001/source/page_01.pdf",
            "cases/case_001/reference.step",
            "cases/case_001/views/view_01_native.png",
            "scripts/__pycache__/helper.cpython-312.pyc",
        ):
            self.assertFalse((published_bundle / relative).exists(), relative)

        copied_manifest = output / self.manifest.relative_to(self.repo)
        self.assertEqual(copied_manifest.read_bytes(), self.manifest.read_bytes())

        published_legacy = output / self.legacy_demo.relative_to(self.repo)
        for relative in (
            "index.html",
            "render_preview.py",
            "assets/case-005-original.webp",
            "assets/case-005-normalized.png",
            "assets/case-005-physical_mm.png",
            "assets/case-005.json",
        ):
            self.assertEqual(
                (published_legacy / relative).read_bytes(),
                (self.legacy_demo / relative).read_bytes(),
                relative,
            )
        self.assertFalse((published_legacy / "local/reference.step").exists())
        self.assertFalse((published_legacy / "__pycache__/render_preview.pyc").exists())
        self.assertFalse((output / self.unlisted_demo.relative_to(self.repo)).exists())

    def test_source_and_public_bundle_assets_are_immutable(self) -> None:
        bundle = self.make_bundle()
        registered = self.register_bundle(bundle)
        self.assertEqual(registered.returncode, 0, registered.stderr)

        self.old_source.write_text("changed old report", encoding="utf-8")
        changed_source = self.build(self.repo / "_site-source-change")
        self.assertNotEqual(changed_source.returncode, 0)
        self.assertIn("historical report changed", changed_source.stderr)

        self.old_source.write_text(
            "<!doctype html><title>old three-case report</title>", encoding="utf-8"
        )
        (bundle / "app.js").write_text("changed public asset", encoding="utf-8")
        changed_bundle = self.build(self.repo / "_site-bundle-change")
        self.assertNotEqual(changed_bundle.returncode, 0)
        self.assertIn("historical report bundle changed", changed_bundle.stderr)


if __name__ == "__main__":
    unittest.main()
