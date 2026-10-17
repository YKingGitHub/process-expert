#!/usr/bin/env python3
"""Independently verify that exported CAD files use the declared transform.

The ordinary rigid round-trip check only proves that the published matrices are
mutual inverses.  This release check instead reloads the exported STEP files and
compares their actual bounds with source bounds transformed by the published
raw-to-canonical matrix.  All released rotations are signed axis permutations,
so transforming the eight source-bbox corners gives the exact expected AABB.
"""

import argparse
import itertools
import json
import math
import os
from pathlib import Path
import tempfile

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from alignment_math import axis_angle, basis, determinant, point


BASE = Path(__file__).resolve().parents[1]
V1 = BASE.parent / "2026-10-15-real-triplets-33-v1"
DEFAULT_TOLERANCE_MM = 1e-5


def bounds(shape):
    box = Bnd_Box()
    box.SetGap(0)
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    return list(box.Get())


def bbox_corners(box):
    return itertools.product(*[(box[i], box[i + 3]) for i in range(3)])


def transformed_bounds(box, transform):
    transformed = [point(transform, corner) for corner in bbox_corners(box)]
    return [min(p[i] for p in transformed) for i in range(3)] + [
        max(p[i] for p in transformed) for i in range(3)
    ]


def max_abs_error(left, right):
    return max(abs(a - b) for a, b in zip(left, right))


def is_signed_axis_permutation(rotation):
    snapped = [[round(value) for value in row] for row in rotation]
    entries = (
        (value, integer)
        for row, integers in zip(rotation, snapped)
        for value, integer in zip(row, integers)
    )
    if any(abs(value - integer) > 1e-12 for value, integer in entries):
        return False
    return all(sum(abs(value) for value in row) == 1 for row in snapped) and all(
        sum(abs(snapped[row][column]) for row in range(3)) == 1
        for column in range(3)
    )


def verify_cadquery_rotation_contract(tolerance_mm):
    """Check all 24 signed-axis rotations against an asymmetric real solid."""
    # Deliberately unequal extents and an off-origin center make every axis and
    # sign observable from the resulting bounds.
    raw = cq.Workplane("XY").box(3.0, 11.0, 7.0).translate((3.5, -1.5, 13.5)).val()
    raw_bounds = bounds(raw)
    axes = (
        (1, 0, 0),
        (-1, 0, 0),
        (0, 1, 0),
        (0, -1, 0),
        (0, 0, 1),
        (0, 0, -1),
    )
    checks = []
    for right, up in itertools.product(axes, repeat=2):
        if sum(a * b for a, b in zip(right, up)):
            continue
        rotation = basis(right, up)
        axis, degrees = axis_angle(rotation)
        rotated = raw.rotate((0, 0, 0), axis, degrees)
        homogeneous = [row + [0.0] for row in rotation] + [[0, 0, 0, 1]]
        expected = transformed_bounds(raw_bounds, homogeneous)
        actual = bounds(rotated)
        error = max_abs_error(expected, actual)
        checks.append(
            {
                "right": list(right),
                "up": list(up),
                "axis": axis,
                "degrees": degrees,
                "max_abs_bounds_error_mm": error,
            }
        )
    maximum = max(item["max_abs_bounds_error_mm"] for item in checks)
    return {
        "status": "passed" if len(checks) == 24 and maximum <= tolerance_mm else "failed",
        "rotation_count": len(checks),
        "max_abs_bounds_error_mm": maximum,
        "tolerance_mm": tolerance_mm,
        "method": "asymmetric off-origin CadQuery solid; expected AABB from matrix-transformed bbox corners",
        "checks": checks,
    }


def verify_export(label, source_bounds, exported_path, transform, tolerance_mm):
    expected = transformed_bounds(source_bounds, transform)
    exported = cq.importers.importStep(str(exported_path)).val()
    actual = bounds(exported)
    error = max_abs_error(expected, actual)
    return {
        "status": "passed" if error <= tolerance_mm else "failed",
        "source_bounds_mm": source_bounds,
        "expected_bounds_mm": expected,
        "actual_exported_bounds_mm": actual,
        "max_abs_bounds_error_mm": error,
        "tolerance_mm": tolerance_mm,
        "export": label,
    }


def write_json_atomic(path, data):
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def verify_case(case_id, rotation_regression, tolerance_mm, write):
    case = BASE / "cases" / case_id
    alignment_path = case / "alignment.json"
    data = json.loads(alignment_path.read_text())
    if data.get("status") != "pose_calibrated_candidate":
        return {"case_id": case_id, "status": "skipped", "reason": data.get("status")}

    transform = data["raw_to_canonical"]
    if len(transform) != 4 or any(len(row) != 4 for row in transform):
        raise ValueError(f"{case_id}: raw_to_canonical must be 4x4")
    rotation = [row[:3] for row in transform[:3]]
    if any(sorted(abs(v) for v in row) != [0, 0, 1] for row in rotation):
        raise ValueError(f"{case_id}: AABB-corner verifier requires signed axis permutations")
    basis(rotation[0], rotation[1])
    if abs(determinant(rotation) - 1) > 1e-7:
        raise ValueError(f"{case_id}: transform rotation is not proper")
    if not is_signed_axis_permutation(rotation):
        raise ValueError(
            f"{case_id}: bbox-corner verification requires a signed axis permutation"
        )

    source_reference = cq.importers.importStep(
        str(V1 / "cases" / case_id / "reference.step")
    ).val()
    reference = verify_export(
        "reference.step",
        bounds(source_reference),
        case / "reference.step",
        transform,
        tolerance_mm,
    )
    source_reconstructed_bounds = data["legacy_geometry_validation"]["reconstructed"][
        "bounds_mm"
    ]
    reconstructed = verify_export(
        "reconstructed.step",
        source_reconstructed_bounds,
        case / "reconstructed.step",
        transform,
        tolerance_mm,
    )
    status = (
        "passed"
        if rotation_regression["status"] == reference["status"] == reconstructed["status"] == "passed"
        else "failed"
    )
    verification = {
        "status": status,
        "method": "export/reload AABB versus source AABB corners transformed by raw_to_canonical",
        "signed_axis_permutation_required": True,
        "cadquery_rotation_contract": {
            key: value for key, value in rotation_regression.items() if key != "checks"
        },
        "reference": reference,
        "reconstructed": reconstructed,
    }
    data["export_coordinate_verification"] = verification
    # This verifier never upgrades acceptance or training state.  A failure is
    # persisted as evidence and returned nonzero by main.
    if data.get("training_ready") is not False:
        raise ValueError(f"{case_id}: verifier refuses a training-ready input")
    if write:
        write_json_atomic(alignment_path, data)
    return {"case_id": case_id, "status": status, "verification": verification}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*")
    parser.add_argument("--tolerance-mm", type=float, default=DEFAULT_TOLERANCE_MM)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.tolerance_mm) or args.tolerance_mm <= 0:
        raise ValueError("tolerance must be positive and finite")

    regression = verify_cadquery_rotation_contract(args.tolerance_mm)
    if regression["status"] != "passed":
        raise SystemExit(json.dumps({"cadquery_rotation_contract": regression}, indent=2))
    chosen = args.cases or [f"case_{i:03d}" for i in range(1, 34)]
    results = [
        verify_case(case_id, regression, args.tolerance_mm, not args.check_only)
        for case_id in chosen
    ]
    summary = {
        "cadquery_rotation_contract": {
            key: value for key, value in regression.items() if key != "checks"
        },
        "results": [
            {
                "case_id": item["case_id"],
                "status": item["status"],
                **(
                    {
                        "reference_max_abs_bounds_error_mm": item["verification"][
                            "reference"
                        ]["max_abs_bounds_error_mm"],
                        "reconstructed_max_abs_bounds_error_mm": item[
                            "verification"
                        ]["reconstructed"]["max_abs_bounds_error_mm"],
                    }
                    if item["status"] in {"passed", "failed"}
                    else {"reason": item["reason"]}
                ),
            }
            for item in results
        ],
    }
    print(json.dumps(summary, indent=2))
    if any(item["status"] == "failed" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
