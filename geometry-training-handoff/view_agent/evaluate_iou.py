#!/usr/bin/env python3
"""Score View Agent STEP outputs with Ortho2CAD's scale-aligned solid IoU."""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import statistics
from pathlib import Path

import cadquery as cq
import numpy as np


def cq_align_shapes(
    source: cq.Workplane, target: cq.Workplane
) -> tuple[cq.Workplane | None, float, cq.Vector, cq.Vector]:
    """Match the principal-axis and scale alignment used by Ortho2CAD."""
    c_source = cq.Shape.centerOfMass(source.val())
    c_target = cq.Shape.centerOfMass(target.val())
    inertia_source = np.array(cq.Shape.matrixOfInertia(source.val()))
    inertia_target = np.array(cq.Shape.matrixOfInertia(target.val()))
    volume_source = cq.Shape.computeMass(source.val())
    volume_target = cq.Shape.computeMass(target.val())
    eigen_source, vectors_source = np.linalg.eigh(inertia_source)
    eigen_target, vectors_target = np.linalg.eigh(inertia_target)
    if volume_source <= 0 or volume_target <= 0:
        return None, 0.0, c_source, c_target

    scale_source = np.sqrt(np.abs(eigen_source).sum() / volume_source)
    scale_target = np.sqrt(np.abs(eigen_target).sum() / volume_target)
    normalized_source = source.translate(-c_source).val().scale(1 / scale_source)
    normalized_target = target.translate(-c_target).val().scale(1 / scale_target)
    rotations = np.zeros((4, 3, 3))
    rotations[0] = vectors_target @ vectors_source.T
    for index in range(3):
        alignment = 1 - 2 * np.array(
            [index > 0, (index + 1) % 2, index % 3 <= 1]
        )
        rotations[index + 1] = vectors_target @ (
            alignment[None, :] * vectors_source
        ).T

    best_iou = 0.0
    best_transform = None
    for rotation in rotations:
        transform = np.zeros((4, 4))
        transform[:3, :3] = rotation
        transform[-1, -1] = 1
        aligned = normalized_source.transformGeometry(cq.Matrix(transform.tolist()))
        try:
            intersection = aligned.intersect(normalized_target)
            union = aligned.fuse(normalized_target)
            iou = float(intersection.Volume() / union.Volume())
        except Exception:
            iou = 0.0
        if iou > best_iou:
            best_iou = iou
            best_transform = transform
    best_iou = min(1.0, max(0.0, best_iou))
    if best_transform is None:
        return None, best_iou, c_source, c_target
    aligned = (
        normalized_source.transformGeometry(cq.Matrix(best_transform.tolist()))
        .scale(scale_target)
        .translate(c_target)
    )
    return cq.Workplane(aligned), best_iou, c_source, c_target


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def score_worker(predicted_path: str, truth_path: str, queue) -> None:
    try:
        predicted = cq.importers.importStep(predicted_path)
        truth = cq.importers.importStep(truth_path)
        _aligned, iou, _source_center, _target_center = cq_align_shapes(
            predicted, truth
        )
        queue.put({"status": "SCORED", "iou": float(iou)})
    except Exception as exc:
        queue.put(
            {
                "status": "SCORE_FAIL",
                "iou": 0.0,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )


def score_with_timeout(
    predicted_path: Path, truth_path: Path, timeout_seconds: float
) -> dict[str, object]:
    context = mp.get_context("fork")
    queue = context.Queue(maxsize=1)
    process = context.Process(
        target=score_worker,
        args=(str(predicted_path), str(truth_path), queue),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join()
        queue.close()
        return {
            "status": "SCORE_TIMEOUT",
            "iou": 0.0,
            "error_type": "TimeoutExpired",
            "error": f"IoU scoring exceeded {timeout_seconds} seconds",
        }
    if queue.empty():
        queue.close()
        return {
            "status": "SCORE_FAIL",
            "iou": 0.0,
            "error_type": "MissingWorkerResult",
            "error": f"worker exited with code {process.exitcode}",
        }
    result = queue.get()
    queue.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--generation-dir", type=Path, required=True)
    parser.add_argument("--iou-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.iou_timeout_seconds <= 0:
        parser.error("--iou-timeout-seconds must be positive")

    manifest_path = args.manifest.resolve()
    generation_dir = args.generation_dir.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("purpose") != "post_inference_evaluation_only":
        raise ValueError("evaluation-only manifest required")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("manifest has no samples")

    rows: list[dict[str, object]] = []
    valid_ious: list[float] = []
    generated_step_count = 0
    for sample in samples:
        case_id = str(sample["id"])
        result_path = generation_dir / case_id / "result.json"
        predicted_path = generation_dir / case_id / "generated.step"
        truth_path = Path(str(sample["ground_truth_step"]))
        generation_status = "NOT_RUN"
        if result_path.is_file():
            try:
                generation_status = str(
                    json.loads(result_path.read_text(encoding="utf-8")).get("status")
                )
            except (OSError, json.JSONDecodeError):
                generation_status = "INVALID_RESULT"
        row: dict[str, object] = {
            "id": case_id,
            "name": sample.get("name"),
            "generation_status": generation_status,
            "ground_truth_step": str(truth_path),
            "predicted_step": str(predicted_path),
            "normalized_iou": 0.0,
            "scoring_status": "INVALID_OR_MISSING_STEP",
        }
        if generation_status == "STEP_EXPORTED" and predicted_path.is_file():
            generated_step_count += 1
            score = score_with_timeout(
                predicted_path, truth_path, args.iou_timeout_seconds
            )
            row["scoring_status"] = score["status"]
            row["normalized_iou"] = float(score["iou"])
            if score["status"] == "SCORED":
                valid_ious.append(float(score["iou"]))
            else:
                row["error_type"] = score.get("error_type")
                row["error"] = score.get("error")
        rows.append(row)
        print(
            f"{case_id}: {row['scoring_status']} iou={row['normalized_iou']}",
            flush=True,
        )

    all_ious = [float(row["normalized_iou"]) for row in rows]
    count = len(rows)
    scoring_status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row["scoring_status"])
        scoring_status_counts[status] = scoring_status_counts.get(status, 0) + 1
    summary = {
        "schema_version": 1,
        "metric": "Ortho2CAD principal-axis and scale aligned solid IoU",
        "manifest": str(manifest_path),
        "generation_dir": str(generation_dir),
        "sample_count": count,
        "generated_step_count": generated_step_count,
        "step_export_rate": generated_step_count / count,
        "scored_step_count": len(valid_ious),
        "scored_step_rate": len(valid_ious) / count,
        "scoring_status_counts": scoring_status_counts,
        "average_iou_valid_steps": (
            statistics.fmean(valid_ious) if valid_ious else None
        ),
        "median_iou_valid_steps": (
            statistics.median(valid_ious) if valid_ious else None
        ),
        "p25_iou_valid_steps": percentile(valid_ious, 0.25),
        "p75_iou_valid_steps": percentile(valid_ious, 0.75),
        "average_iou_all_samples_invalid_zero": statistics.fmean(all_ious),
        "all_sample_threshold_counts": {
            "iou_ge_0_5": sum(value >= 0.5 for value in all_ious),
            "iou_ge_0_8": sum(value >= 0.8 for value in all_ious),
            "iou_ge_0_9": sum(value >= 0.9 for value in all_ious),
        },
        "all_sample_threshold_rates": {
            "iou_ge_0_5": sum(value >= 0.5 for value in all_ious) / count,
            "iou_ge_0_8": sum(value >= 0.8 for value in all_ious) / count,
            "iou_ge_0_9": sum(value >= 0.9 for value in all_ious) / count,
        },
    }
    payload = {"summary": summary, "samples": rows}
    (generation_dir / "iou_evaluation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (generation_dir / "iou_evaluation.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        columns = [
            "id",
            "name",
            "generation_status",
            "scoring_status",
            "normalized_iou",
            "ground_truth_step",
            "predicted_step",
            "error_type",
            "error",
        ]
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
