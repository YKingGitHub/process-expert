#!/usr/bin/env python3
"""Lightweight integrity checks for the 33-case review dataset.

The test intentionally uses only the Python standard library.  Geometry QA is
reported by validation.json; passing that gate is never treated here as human
acceptance or permission to train.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import unittest
import zipfile


BASE = Path(__file__).resolve().parents[1]
CASES = BASE / "cases"
EXPECTED_CASE_IDS = tuple(f"case_{number:03d}" for number in range(1, 34))
STANDARD_ROLES = ("front", "top", "side")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe artifact path: {value!r}")
    if any("\\" in part for part in path.parts):
        raise ValueError(f"non-POSIX artifact path: {value!r}")
    return path


def case_path(case_dir: Path, value: str) -> Path:
    relative = safe_relative_path(value)
    return case_dir.joinpath(*relative.parts)


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE:
        raise ValueError(f"not a PNG file: {path}")
    if header[12:16] != b"IHDR":
        raise ValueError(f"PNG does not start with IHDR: {path}")
    return struct.unpack(">II", header[16:24])


class ModelAudit(ast.NodeVisitor):
    """Reject imports and calls that could read surrogate geometry."""

    allowed_imports = {"cadquery", "math"}
    forbidden_names = {"open", "eval", "exec", "__import__", "compile"}
    forbidden_attributes = {
        "importStep",
        "importDXF",
        "importShape",
        "load",
        "loadShape",
        "read",
        "read_bytes",
        "read_text",
    }
    embedded_markers = (
        "iso-10303-21",
        "dbrep_drawableshape",
        "ground_truth.step",
        "reference.step",
        "base64,",
    )

    def __init__(self) -> None:
        self.issues: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for name in node.names:
            if name.name not in self.allowed_imports:
                self.issues.append(f"unsupported import {name.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module not in self.allowed_imports:
            self.issues.append(f"unsupported import from {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        function = node.func
        if isinstance(function, ast.Name) and function.id in self.forbidden_names:
            self.issues.append(f"forbidden call {function.id}")
        if isinstance(function, ast.Attribute):
            chain = []
            current = function
            while isinstance(current, ast.Attribute):
                chain.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                chain.append(current.id)
            if function.attr in self.forbidden_attributes or "importers" in chain:
                self.issues.append(
                    "forbidden geometry or file read " + ".".join(reversed(chain))
                )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        if isinstance(node.value, str):
            lowered = node.value.lower()
            if any(marker in lowered for marker in self.embedded_markers):
                self.issues.append("embedded or referenced external geometry marker")
            if len(node.value) > 50_000:
                self.issues.append("suspiciously large embedded string")
            if any(ext in lowered for ext in (".step", ".stp", ".brep")):
                if lowered.strip() != "reconstructed.step":
                    self.issues.append("unexpected geometry filename literal")
        self.generic_visit(node)


class DatasetLayoutTests(unittest.TestCase):
    def test_exactly_33_case_directories(self) -> None:
        actual = tuple(sorted(path.name for path in CASES.glob("case_*") if path.is_dir()))
        self.assertEqual(actual, EXPECTED_CASE_IDS)

    def test_required_unpacked_artifacts_exist(self) -> None:
        required = (
            "model.py",
            "authoring.json",
            "views.json",
            "structured_views.webp",
            "reference.step",
            "reconstructed.step",
            "verified_reconstructed.step",
            "validation.json",
        )
        for case_id in EXPECTED_CASE_IDS:
            with self.subTest(case=case_id):
                case_dir = CASES / case_id
                for name in required:
                    path = case_dir / name
                    self.assertTrue(path.is_file(), f"missing {path}")
                    self.assertGreater(path.stat().st_size, 0, f"empty {path}")

    def test_normalized_view_pngs_are_1024_square(self) -> None:
        normalized_count = 0
        for case_id in EXPECTED_CASE_IDS:
            case_dir = CASES / case_id
            views = read_json(case_dir / "views.json")
            self.assertEqual(views.get("case_id"), case_id)
            self.assertTrue(views.get("views"), f"{case_id} has no annotated views")
            for view in views["views"]:
                normalized_count += 1
                with self.subTest(case=case_id, view=view.get("id")):
                    self.assertEqual(view.get("canvas_size"), [1024, 1024])
                    image_name = view.get("image")
                    self.assertIsInstance(image_name, str)
                    self.assertEqual(PurePosixPath(image_name).suffix.lower(), ".png")
                    self.assertEqual(
                        png_dimensions(case_path(case_dir, image_name)), (1024, 1024)
                    )
                    native_name = view.get("native_image")
                    self.assertIsInstance(native_name, str)
                    native_size = png_dimensions(case_path(case_dir, native_name))
                    self.assertGreater(native_size[0], 0)
                    self.assertGreater(native_size[1], 0)
        self.assertGreater(normalized_count, 0)

    def test_missing_standard_views_are_not_filled_by_sections(self) -> None:
        for case_id in EXPECTED_CASE_IDS:
            views = read_json(CASES / case_id / "views.json")
            records = views["views"]
            by_id = {record["id"]: record for record in records}
            self.assertEqual(len(by_id), len(records), f"duplicate view ID in {case_id}")
            slots = views.get("standard_slots")
            self.assertEqual(set(slots or {}), set(STANDARD_ROLES))

            assigned = set()
            for role in STANDARD_ROLES:
                selected = slots[role]
                role_ids = {
                    record["id"] for record in records if record.get("role") == role
                }
                if selected is None:
                    self.assertFalse(
                        role_ids,
                        f"{case_id} declares {role} missing but has a {role} view",
                    )
                else:
                    self.assertIn(selected, by_id)
                    self.assertEqual(
                        by_id[selected].get("role"),
                        role,
                        f"{case_id} substitutes a non-{role} view into {role}",
                    )
                    self.assertEqual(role_ids, {selected})
                    assigned.add(selected)

            expected_extras = {
                record["id"]
                for record in records
                if record.get("role") not in STANDARD_ROLES
            }
            actual_extras = set(views.get("extra_view_ids", []))
            self.assertEqual(actual_extras, expected_extras)
            self.assertTrue(assigned.isdisjoint(actual_extras))


class ModelSourceTests(unittest.TestCase):
    def test_models_have_no_external_geometry_reads(self) -> None:
        for case_id in EXPECTED_CASE_IDS:
            path = CASES / case_id / "model.py"
            with self.subTest(case=case_id):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                audit = ModelAudit()
                audit.visit(tree)
                self.assertEqual(audit.issues, [])
                stores_solid = any(
                    isinstance(node, ast.Name)
                    and node.id == "solid"
                    and isinstance(node.ctx, ast.Store)
                    for node in ast.walk(tree)
                )
                self.assertTrue(stores_solid, f"{case_id} has no global solid assignment")


class IndependentValidationTests(unittest.TestCase):
    def test_validation_hashes_match_publication_inputs(self) -> None:
        for case_id in EXPECTED_CASE_IDS:
            case_dir = CASES / case_id
            validation = read_json(case_dir / "validation.json")
            with self.subTest(case=case_id):
                self.assertEqual(validation.get("case_id"), case_id)
                self.assertEqual(validation.get("execution_status"), "success")
                self.assertEqual(
                    validation.get("validator_sha256"),
                    sha256_path(BASE / "scripts" / "validate_case.py"),
                )
                if validation.get("boolean_status") == "error":
                    self.assertEqual(validation.get("status"), "geometry_check_error")
                    self.assertIs(validation.get("geometry_gate_pass"), False)
                    self.assertTrue(validation.get("error"))
                    for metric in ("intersection_volume_mm3", "iou_same_frame", "symmetric_difference_volume_mm3", "symmetric_difference_over_reference_volume"):
                        self.assertIsNone(validation["metrics"][metric])
                self.assertEqual(validation.get("program_audit", {}).get("status"), "passed")
                self.assertIs(
                    validation.get("program_audit", {}).get("external_geometry_reads"),
                    False,
                )
                self.assertEqual(
                    validation.get("model_sha256"), sha256_path(case_dir / "model.py")
                )
                self.assertEqual(
                    validation.get("reference_sha256"),
                    sha256_path(case_dir / "reference.step"),
                )
                self.assertEqual(
                    validation.get("reconstructed_sha256"),
                    sha256_path(case_dir / "verified_reconstructed.step"),
                )
                self.assertIs(validation.get("training_ready"), False)


class PackagedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset_path = BASE / "dataset.json"
        if not dataset_path.is_file():
            raise unittest.SkipTest(
                "dataset.json and per-case ZIPs are not materialized yet"
            )
        cls.dataset = read_json(dataset_path)

    def test_dataset_index_and_training_state(self) -> None:
        samples = self.dataset.get("samples", [])
        by_id = {sample["id"]: sample for sample in samples}
        self.assertEqual(set(by_id), set(EXPECTED_CASE_IDS))
        self.assertEqual(len(samples), 33)
        self.assertEqual(self.dataset.get("summary", {}).get("case_count"), 33)
        self.assertEqual(
            self.dataset.get("summary", {}).get("training_ready_count"), 0
        )
        self.assertEqual(read_json(BASE / "summary.json"), self.dataset["summary"])

        for case_id, sample in by_id.items():
            with self.subTest(case=case_id):
                self.assertIs(sample["triplet"].get("training_ready"), False)
                self.assertIs(sample["validation"].get("training_ready"), False)
                self.assertEqual(sample["triplet"].get("acceptance_status"), "pending")

    def test_zip_contents_and_manifest_hashes(self) -> None:
        samples = {sample["id"]: sample for sample in self.dataset["samples"]}
        for case_id in EXPECTED_CASE_IDS:
            case_dir = CASES / case_id
            sample = samples[case_id]
            manifest_path = case_dir / "triplet.json"
            archive_path = case_dir / "triplet.zip"
            with self.subTest(case=case_id):
                manifest = read_json(manifest_path)
                self.assertEqual(manifest, sample["triplet"])
                self.assertEqual(sample.get("download"), f"cases/{case_id}/triplet.zip")
                self.assertEqual(
                    sample.get("download_sha256"), sha256_path(archive_path)
                )
                self.assertIs(manifest.get("training_ready"), False)
                self.assertEqual(manifest.get("independent_reference_step"), "reference.step")
                self.assertIn("verified_reconstructed.step", manifest.get("output_step_source", ""))

                hashes = manifest.get("sha256")
                self.assertIsInstance(hashes, dict)
                self.assertTrue(hashes)
                expected_relative = set(hashes) | {"triplet.json"}
                prefix = f"{case_id}/"

                with zipfile.ZipFile(archive_path, "r") as archive:
                    names = archive.namelist()
                    self.assertEqual(len(names), len(set(names)), "duplicate ZIP entry")
                    self.assertTrue(all(name.startswith(prefix) for name in names))
                    relative_names = {name[len(prefix) :] for name in names}
                    self.assertEqual(relative_names, expected_relative)
                    self.assertFalse(
                        any(PurePosixPath(name).suffix.lower() == ".pdf" for name in names)
                    )
                    self.assertEqual(
                        archive.read(prefix + "triplet.json"),
                        manifest_path.read_bytes(),
                    )

                    for relative_name, expected_hash in hashes.items():
                        safe_relative_path(relative_name)
                        zipped = archive.read(prefix + relative_name)
                        self.assertEqual(sha256_bytes(zipped), expected_hash)
                        if relative_name == "reconstructed.step":
                            local = case_dir / "verified_reconstructed.step"
                        else:
                            local = case_path(case_dir, relative_name)
                        self.assertTrue(local.is_file(), f"missing hashed file {local}")
                        self.assertEqual(sha256_path(local), expected_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)
