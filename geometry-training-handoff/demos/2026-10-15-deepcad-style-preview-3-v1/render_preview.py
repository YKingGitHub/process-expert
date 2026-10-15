#!/usr/bin/env python3
"""Render a STEP solid as a canonical DeepCAD-style 800x800 drawing.

This prototype intentionally starts from ground-truth STEP geometry.  It is an
upper-bound experiment for geometry-domain alignment, not a PDF-cleaning tool.

The renderer reuses Ortho2CAD's original pythonocc HLR implementation.  It
canonicalizes the STEP axes by mapping longest/middle/shortest bounding-box
axes to X/Y/Z, writes both normalized (training probe) and millimetre-labelled
variants, and records the reversible transform in JSON.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types


def sha256_file(path):
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_renderer(path):
    # The source module imports cairosvg for an unrelated CLI path.  The CAD
    # environment used here does not need it when exporting SVG directly.
    try:
        import cairosvg  # noqa: F401
    except ImportError:
        sys.modules["cairosvg"] = types.ModuleType("cairosvg")

    spec = importlib.util.spec_from_file_location("ortho_renderer", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load renderer: {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_bounds(shape):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    box = Bnd_Box()
    box.SetGap(0.0)
    brepbndlib.AddOptimal(shape, box, False, False)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {
        "x": float(xmax - xmin),
        "y": float(ymax - ymin),
        "z": float(zmax - zmin),
    }


def matrix_determinant(matrix):
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def canonical_axis_matrix(bounds):
    """Return a right-handed longest/middle/shortest -> X/Y/Z matrix."""
    names = ["x", "y", "z"]
    # Round away sub-micron numerical noise so equal cylindrical axes retain
    # the STEP file's stable X/Y/Z order.
    ordered = sorted(
        range(3), key=lambda idx: (-round(bounds[names[idx]], 6), idx)
    )
    matrix = [[0.0, 0.0, 0.0] for _ in range(3)]
    for new_axis, old_axis in enumerate(ordered):
        matrix[new_axis][old_axis] = 1.0

    # An odd permutation is a reflection.  Flip canonical Z so the transform
    # remains a proper rotation while preserving every bounding-box length.
    if matrix_determinant(matrix) < 0:
        matrix[2] = [-value for value in matrix[2]]
    return matrix


def transform_shape(shape, matrix):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Trsf

    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    if matrix == identity:
        return shape

    trsf = gp_Trsf()
    trsf.SetValues(
        matrix[0][0],
        matrix[0][1],
        matrix[0][2],
        0.0,
        matrix[1][0],
        matrix[1][1],
        matrix[1][2],
        0.0,
        matrix[2][0],
        matrix[2][1],
        matrix[2][2],
        0.0,
    )
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def count_solids(shape):
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer

    count = 0
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def dimension_payload(bounds):
    # SVGExporter expects width=X, depth=Y, height=Z.
    return {
        "width": bounds["x"],
        "depth": bounds["y"],
        "height": bounds["z"],
    }


def axis_map_labels(matrix):
    old_names = ["old_x", "old_y", "old_z"]
    labels = {}
    for new_idx, new_name in enumerate(["new_x", "new_y", "new_z"]):
        for old_idx, value in enumerate(matrix[new_idx]):
            if value:
                labels[new_name] = ("+" if value > 0 else "-") + old_names[old_idx]
                break
    return labels


def rasterize(svg_path, png_path, firefox):
    with tempfile.TemporaryDirectory(prefix="deepcad-firefox-") as profile:
        command = [
            firefox,
            "--headless",
            "--no-remote",
            "--profile",
            profile,
            "--screenshot",
            str(png_path.resolve()),
            "--window-size",
            "800,800",
            svg_path.resolve().as_uri(),
        ]
        env = dict(os.environ)
        env["MOZ_HEADLESS"] = "1"
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=90,
        )
    if completed.returncode != 0 or not png_path.exists():
        output = completed.stdout.decode("utf-8", errors="replace")
        raise RuntimeError("Firefox rasterization failed: {}".format(output))
    with open(str(png_path), "rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Rasterizer did not produce a valid PNG")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", required=True, type=Path)
    parser.add_argument("--renderer", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--part-name", required=True)
    parser.add_argument("--source-drawing-name", required=True)
    parser.add_argument("--firefox", default="firefox")
    parser.add_argument("--normalization-max", default=1.5, type=float)
    parser.add_argument("--keep-svg", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    renderer = load_renderer(args.renderer)

    started = time.time()
    projector = renderer.OrthographicProjector(str(args.step))
    original_bounds = exact_bounds(projector.shape)
    axis_matrix = canonical_axis_matrix(original_bounds)
    projector.shape = transform_shape(projector.shape, axis_matrix)
    canonical_bounds = exact_bounds(projector.shape)
    solid_count = count_solids(projector.shape)
    views = projector.generate_standard_views()
    hlr_seconds = time.time() - started

    longest = max(canonical_bounds.values())
    normalization_scale = args.normalization_max / longest
    normalized_bounds = {
        key: value * normalization_scale for key, value in canonical_bounds.items()
    }

    exporter = renderer.SVGExporter(width=600, height=600)
    stem = args.case_id.replace("_", "-")
    generated = {}
    with tempfile.TemporaryDirectory(prefix="deepcad-preview-") as temporary:
        temporary_dir = Path(temporary)
        variants = {
            "normalized": normalized_bounds,
            "physical_mm": canonical_bounds,
        }
        for variant, labels in variants.items():
            svg_path = temporary_dir / "{}-{}.svg".format(stem, variant)
            png_path = args.output_dir / "{}-{}.png".format(stem, variant)
            exporter.export_combined_views(
                views,
                str(svg_path),
                include_dimensions=True,
                actual_dimensions=dimension_payload(labels),
            )
            rasterize(svg_path, png_path, args.firefox)
            generated[variant] = {
                "file": png_path.name,
                "sha256": sha256_file(png_path),
            }
            if args.keep_svg:
                kept_svg = args.output_dir / svg_path.name
                kept_svg.write_bytes(svg_path.read_bytes())

    metadata = {
        "schema_version": 1,
        "case_id": args.case_id,
        "part_name": args.part_name,
        "source_drawing_name": args.source_drawing_name,
        "input": {
            "step_file": args.step.name,
            "step_sha256": sha256_file(args.step),
            "solid_count": solid_count,
        },
        "method": {
            "description": "Ground-truth STEP re-rendered with Ortho2CAD pythonocc HLR",
            "canvas_px": [800, 800],
            "views": {
                "right": "+X to -X",
                "front": "+Y to -Y",
                "top": "+Z to -Z",
            },
            "canonical_axis_rule": "longest/middle/shortest bbox axes -> X/Y/Z",
            "canonical_axis_map": axis_map_labels(axis_matrix),
            "transform_matrix": axis_matrix,
            "renderer_file": args.renderer.name,
            "renderer_sha256": sha256_file(args.renderer),
            "hlr_seconds": round(hlr_seconds, 3),
        },
        "dimensions": {
            "original_step_mm": original_bounds,
            "canonical_mm": canonical_bounds,
            "normalized": normalized_bounds,
            "normalization": "max bbox dimension -> {:.4f}".format(
                args.normalization_max
            ),
            "scale_per_mm": normalization_scale,
        },
        "outputs": generated,
        "scope_warning": (
            "This uses ground-truth STEP geometry; it does not prove automatic "
            "view extraction or cleanup from the source PDF."
        ),
    }
    metadata_path = args.output_dir / "{}.json".format(stem)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
