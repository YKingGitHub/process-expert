#!/usr/bin/env python3
"""Build the isolated 33-part drawing/STEP benchmark from the source ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo


STEP_SUFFIXES = {".step", ".stp"}
PART_CODE = re.compile(r"(?<!\d)(\d{5}-\d+)(?!\d)")


def decoded_zip_name(name: str) -> str:
    """Repair archives whose UTF-8 names were stored without the UTF-8 flag."""
    try:
        return name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else normalized(part) for part in re.split(r"(\d+)", value)]


def usable_member(info: ZipInfo) -> bool:
    path = PurePosixPath(decoded_zip_name(info.filename))
    return (
        not info.is_dir()
        and "__MACOSX" not in path.parts
        and not path.name.startswith("._")
        and not path.is_absolute()
        and ".." not in path.parts
    )


def pair_drawings(infos: list[ZipInfo]) -> list[dict[str, object]]:
    records = [(info, PurePosixPath(decoded_zip_name(info.filename))) for info in infos]
    steps = [(info, path) for info, path in records if path.suffix.casefold() in STEP_SUFFIXES]
    pdfs = [(info, path) for info, path in records if path.suffix.casefold() == ".pdf"]
    pairs: list[dict[str, object]] = []
    for step_info, step_path in steps:
        exact = [
            (pdf_info, pdf_path)
            for pdf_info, pdf_path in pdfs
            if pdf_path.parent == step_path.parent
            and normalized(pdf_path.stem) == normalized(step_path.stem)
        ]
        pairing = "exact_stem"
        matches = exact
        if not matches:
            code = PART_CODE.search(step_path.stem)
            matches = (
                [
                    (pdf_info, pdf_path)
                    for pdf_info, pdf_path in pdfs
                    if pdf_path.parent == step_path.parent
                    and PART_CODE.search(pdf_path.stem)
                    and PART_CODE.search(pdf_path.stem).group(1) == code.group(1)
                ]
                if code
                else []
            )
            pairing = "same_part_code"
        if matches:
            matches.sort(key=lambda item: natural_key(item[1].name))
            pairs.append(
                {
                    "step_info": step_info,
                    "step_path": step_path,
                    "pdfs": matches,
                    "pairing": pairing,
                }
            )
    return pairs


def measure_step(path: Path) -> dict[str, object]:
    import cadquery as cq

    imported = cq.importers.importStep(str(path))
    solids = imported.solids().vals()
    if not solids:
        raise ValueError("STEP contains no solids")
    if any(not solid.isValid() for solid in solids):
        raise ValueError("STEP contains an invalid solid")
    volume = sum(float(solid.Volume()) for solid in solids)
    area = sum(float(solid.Area()) for solid in solids)
    bbox = imported.val().BoundingBox()
    dimensions = [float(bbox.xlen), float(bbox.ylen), float(bbox.zlen)]
    if volume <= 0 or area <= 0 or min(dimensions) <= 0:
        raise ValueError("STEP has non-positive geometry metrics")
    return {
        "solid_count": len(solids),
        "volume_mm3": round(volume, 6),
        "surface_area_mm2": round(area, 6),
        "bbox_mm": {
            "x": round(dimensions[0], 6),
            "y": round(dimensions[1], 6),
            "z": round(dimensions[2], 6),
        },
        "bbox_sorted_mm": [round(value, 6) for value in sorted(dimensions)],
    }


def archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def render_pdf(pdf_path: Path, output_prefix: Path, dpi: int) -> list[Path]:
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(output_prefix)],
        check=True,
        capture_output=True,
        text=True,
    )
    pages = sorted(output_prefix.parent.glob(f"{output_prefix.name}-*.png"), key=lambda p: natural_key(p.name))
    if not pages:
        raise RuntimeError(f"pdftoppm produced no pages for {pdf_path}")
    return pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--expected-pairs", type=int, default=70)
    parser.add_argument("--expected-single-solids", type=int, default=33)
    args = parser.parse_args()

    archive_path = args.archive.resolve()
    output_dir = args.output_dir.resolve()
    if not archive_path.is_file():
        parser.error(f"archive does not exist: {archive_path}")
    if args.dpi <= 0:
        parser.error("--dpi must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)

    classified: list[dict[str, object]] = []
    with ZipFile(archive_path) as archive:
        infos = [info for info in archive.infolist() if usable_member(info)]
        pairs = pair_drawings(infos)
        if len(pairs) != args.expected_pairs:
            raise RuntimeError(
                f"expected {args.expected_pairs} unambiguous drawing/STEP pairs, found {len(pairs)}"
            )

        for index, pair in enumerate(pairs, start=1):
            step_info = pair["step_info"]
            assert isinstance(step_info, ZipInfo)
            with tempfile.NamedTemporaryFile(suffix=".step") as temporary:
                temporary.write(archive.read(step_info))
                temporary.flush()
                try:
                    metrics = measure_step(Path(temporary.name))
                    error = None
                except Exception as exc:
                    metrics = None
                    error = f"{type(exc).__name__}: {exc}"
            pair["metrics"] = metrics
            pair["classification_error"] = error
            classified.append(pair)
            print(
                f"[{index:02d}/{len(pairs)}] {decoded_zip_name(step_info.filename)}: "
                f"{metrics['solid_count'] if metrics else error}",
                flush=True,
            )

        singles = [pair for pair in classified if pair["metrics"] and pair["metrics"]["solid_count"] == 1]
        if len(singles) != args.expected_single_solids:
            raise RuntimeError(
                f"expected {args.expected_single_solids} single-solid pairs, found {len(singles)}"
            )
        singles.sort(key=lambda pair: natural_key(str(pair["step_path"])))

        inference_samples: list[dict[str, object]] = []
        evaluation_samples: list[dict[str, object]] = []
        for case_number, pair in enumerate(singles, start=1):
            case_id = f"case_{case_number:03d}"
            case_dir = output_dir / "cases" / case_id
            source_dir = case_dir / "source_pdfs"
            image_dir = case_dir / "images"
            truth_dir = case_dir / "ground_truth"
            source_dir.mkdir(parents=True, exist_ok=True)
            image_dir.mkdir(parents=True, exist_ok=True)
            truth_dir.mkdir(parents=True, exist_ok=True)

            step_info = pair["step_info"]
            assert isinstance(step_info, ZipInfo)
            truth_path = truth_dir / "ground_truth.step"
            truth_path.write_bytes(archive.read(step_info))
            image_paths: list[str] = []
            source_pdf_paths: list[str] = []
            pdf_records = pair["pdfs"]
            assert isinstance(pdf_records, list)
            for sheet_number, (pdf_info, _pdf_archive_path) in enumerate(pdf_records, start=1):
                pdf_path = source_dir / f"sheet_{sheet_number:02d}.pdf"
                pdf_path.write_bytes(archive.read(pdf_info))
                source_pdf_paths.append(str(pdf_path.resolve()))
                prefix = image_dir / f"sheet_{sheet_number:02d}"
                for page_path in render_pdf(pdf_path, prefix, args.dpi):
                    image_paths.append(str(page_path.resolve()))

            step_path = pair["step_path"]
            assert isinstance(step_path, PurePosixPath)
            sample_common = {
                "id": case_id,
                "name": step_path.stem,
                "images": image_paths,
                "source_pdfs": source_pdf_paths,
                "source_pdf_archive_paths": [
                    decoded_zip_name(pdf_info.filename) for pdf_info, _ in pdf_records
                ],
                "pairing": pair["pairing"],
            }
            inference_samples.append(sample_common)
            evaluation_samples.append(
                {
                    "id": case_id,
                    "name": step_path.stem,
                    "ground_truth_step": str(truth_path.resolve()),
                    "ground_truth_metrics": pair["metrics"],
                    "source_step_archive_path": decoded_zip_name(step_info.filename),
                }
            )

    archive_digest = archive_sha256(archive_path)
    common_metadata = {
        "schema_version": 1,
        "archive": str(archive_path),
        "archive_sha256": archive_digest,
        "sample_count": len(inference_samples),
        "render_dpi": args.dpi,
    }
    inference_manifest = {
        **common_metadata,
        "purpose": "model_input_only_no_ground_truth",
        "samples": inference_samples,
    }
    evaluation_manifest = {
        **common_metadata,
        "purpose": "post_inference_evaluation_only",
        "samples": evaluation_samples,
    }
    pairing_counts: dict[str, int] = {}
    for sample in inference_samples:
        key = str(sample["pairing"])
        pairing_counts[key] = pairing_counts.get(key, 0) + 1
    summary = {
        **common_metadata,
        "usable_archive_members": len(infos),
        "unambiguous_pairs": len(classified),
        "single_solid_samples": len(inference_samples),
        "multi_solid_pairs_excluded": sum(
            1 for pair in classified if pair["metrics"] and pair["metrics"]["solid_count"] > 1
        ),
        "invalid_step_pairs_excluded": sum(1 for pair in classified if not pair["metrics"]),
        "pairing_counts": pairing_counts,
        "total_input_images": sum(len(sample["images"]) for sample in inference_samples),
    }
    write_json(output_dir / "inference_manifest.json", inference_manifest)
    write_json(output_dir / "evaluation_manifest.json", evaluation_manifest)
    write_json(output_dir / "dataset_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
