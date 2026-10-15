"""Materialize the hand-authored CadQuery reconstructions for cases 006..019."""

import json
import runpy
import shutil
from pathlib import Path

import cadquery as cq


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    "/hpc2hdd/home/lwang592/projects/.cache/process-expert/"
    "drawing_20260810_single/cases"
)


def main() -> None:
    rows = []
    for number in range(6, 20):
        case_id = f"case_{number:03d}"
        case_dir = ROOT / "cases" / case_id
        model_path = case_dir / "model.py"
        reference_path = case_dir / "reference.step"
        reconstructed_path = case_dir / "reconstructed.step"

        shutil.copy2(
            SOURCE / case_id / "ground_truth" / "ground_truth.step",
            reference_path,
        )
        namespace = runpy.run_path(str(model_path), run_name="__triplet_validation__")
        solid = namespace["solid"]
        cq.exporters.export(solid, str(reconstructed_path))

        shape = solid.val() if isinstance(solid, cq.Workplane) else solid
        box = shape.BoundingBox()
        rows.append(
            {
                "case_id": case_id,
                "valid": shape.isValid(),
                "volume_mm3": shape.Volume(),
                "bbox_mm": [box.xlen, box.ylen, box.zlen],
            }
        )

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
