#!/usr/bin/env python3
"""Extract concise, deterministic geometric evidence from reference STEP files."""

from __future__ import annotations

import json
from collections import Counter
import argparse
from pathlib import Path
import sys

import cadquery as cq


def rounded(value: float, digits: int = 5) -> float:
    return round(float(value), digits)


def vec(vector: object) -> list[float]:
    if hasattr(vector, "x"):
        return [rounded(vector.x), rounded(vector.y), rounded(vector.z)]
    return [rounded(vector.X()), rounded(vector.Y()), rounded(vector.Z())]


def analyze(path: Path) -> dict[str, object]:
    workplane = cq.importers.importStep(str(path))
    shape = workplane.val()
    box = shape.BoundingBox()
    faces = shape.Faces()
    edges = shape.Edges()
    face_types = Counter(face.geomType() for face in faces)
    edge_types = Counter(edge.geomType() for edge in edges)

    cylinders = []
    planes = []
    for face in faces:
        kind = face.geomType()
        if kind == "CYLINDER":
            cylinder = face._geomAdaptor().Cylinder()
            cylinders.append(
                {
                    "radius": rounded(cylinder.Radius()),
                    "axis": vec(cylinder.Axis().Direction()),
                    "center": vec(cylinder.Location()),
                    "area": rounded(face.Area()),
                }
            )
        elif kind == "PLANE":
            center = face.Center()
            normal = face.normalAt(center)
            planes.append(
                {
                    "area": rounded(face.Area()),
                    "center": vec(center),
                    "normal": vec(normal),
                }
            )

    circles = []
    for edge in edges:
        if edge.geomType() == "CIRCLE":
            radius = edge.radius()
            circles.append(
                {
                    "radius": rounded(radius),
                    "length": rounded(edge.Length()),
                    "center": vec(edge.Center()),
                }
            )

    cylinders.sort(key=lambda item: (-item["area"], item["radius"]))
    planes.sort(key=lambda item: -item["area"])
    circles.sort(key=lambda item: (-item["radius"], item["center"]))
    return {
        "path": str(path),
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids()),
        "volume": rounded(shape.Volume()),
        "area": rounded(shape.Area()),
        "bbox": {
            "x": rounded(box.xlen),
            "y": rounded(box.ylen),
            "z": rounded(box.zlen),
            "min": [rounded(box.xmin), rounded(box.ymin), rounded(box.zmin)],
            "max": [rounded(box.xmax), rounded(box.ymax), rounded(box.zmax)],
        },
        "center_of_mass": vec(shape.Center()),
        "topology": {
            "faces": len(faces),
            "edges": len(edges),
            "vertices": len(shape.Vertices()),
            "face_types": dict(sorted(face_types.items())),
            "edge_types": dict(sorted(edge_types.items())),
        },
        "cylinders": cylinders,
        "largest_planes": planes[:20],
        "circles": circles,
    }


def brief(payload: dict[str, object]) -> dict[str, object]:
    cylinder_counts = Counter(
        (
            item["radius"],
            tuple(abs(round(component, 3)) for component in item["axis"]),
        )
        for item in payload["cylinders"]
    )
    plane_counts = Counter(
        tuple(abs(round(component, 3)) for component in item["normal"])
        for item in payload["largest_planes"]
    )
    return {
        key: payload[key]
        for key in (
            "path",
            "valid",
            "solid_count",
            "volume",
            "area",
            "bbox",
            "center_of_mass",
            "topology",
        )
    } | {
        "cylinders_radius_axis_count": [
            {"radius": radius, "axis": list(axis), "count": count}
            for (radius, axis), count in sorted(
                cylinder_counts.items(), key=lambda item: (-item[0][0], item[0][1])
            )
        ],
        "largest_plane_normal_count": [
            {"normal": list(normal), "count": count}
            for normal, count in sorted(plane_counts.items())
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--brief", action="store_true")
    args = parser.parse_args()
    for path in args.paths:
        payload = analyze(path)
        print(json.dumps(brief(payload) if args.brief else payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
