#!/usr/bin/env python3
"""Evaluate generated STEP files against a separately held GT manifest."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from prepare_batch import measure_step


def percent_error(predicted: float, truth: float) -> float:
    if truth == 0:
        raise ValueError("cannot compute percentage error against zero")
    return (predicted - truth) / truth * 100.0


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def describe(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 6) if values else None,
        "median": round(statistics.median(values), 6) if values else None,
        "p90": round(percentile(values, 0.9), 6) if values else None,
        "max": round(max(values), 6) if values else None,
    }


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--generation-dir", type=Path, required=True)
    parser.add_argument("--volume-threshold-pct", type=float, default=2.0)
    parser.add_argument("--surface-threshold-pct", type=float, default=5.0)
    parser.add_argument("--bbox-threshold-pct", type=float, default=2.0)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    generation_dir = args.generation_dir.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("purpose") != "post_inference_evaluation_only":
        raise ValueError("refusing a manifest that is not marked evaluation-only")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("evaluation manifest contains no samples")

    rows: list[dict[str, object]] = []
    for sample in samples:
        case_id = str(sample["id"])
        case_dir = generation_dir / case_id
        result_path = case_dir / "result.json"
        predicted_path = case_dir / "generated.step"
        generation_status = "NOT_RUN"
        if result_path.is_file():
            try:
                generation_status = str(json.loads(result_path.read_text(encoding="utf-8")).get("status"))
            except (OSError, json.JSONDecodeError):
                generation_status = "INVALID_RESULT"
        row: dict[str, object] = {
            "id": case_id,
            "name": sample["name"],
            "generation_status": generation_status,
            "evaluation_status": "NOT_EXPORTED",
            "ground_truth_step": sample["ground_truth_step"],
            "predicted_step": str(predicted_path),
        }
        if generation_status == "STEP_EXPORTED" and predicted_path.is_file():
            try:
                truth = measure_step(Path(str(sample["ground_truth_step"])))
                predicted = measure_step(predicted_path)
                volume_error = percent_error(
                    float(predicted["volume_mm3"]), float(truth["volume_mm3"])
                )
                surface_error = percent_error(
                    float(predicted["surface_area_mm2"]), float(truth["surface_area_mm2"])
                )
                truth_bbox = [float(value) for value in truth["bbox_sorted_mm"]]
                predicted_bbox = [float(value) for value in predicted["bbox_sorted_mm"]]
                bbox_errors = [
                    percent_error(predicted_value, truth_value)
                    for predicted_value, truth_value in zip(predicted_bbox, truth_bbox)
                ]
                bbox_max_abs = max(abs(value) for value in bbox_errors)
                row.update(
                    {
                        "evaluation_status": "MEASURED",
                        "ground_truth_metrics": truth,
                        "predicted_metrics": predicted,
                        "volume_error_pct": round(volume_error, 6),
                        "volume_abs_error_pct": round(abs(volume_error), 6),
                        "surface_area_error_pct": round(surface_error, 6),
                        "surface_area_abs_error_pct": round(abs(surface_error), 6),
                        "bbox_axis_error_pct": [round(value, 6) for value in bbox_errors],
                        "bbox_max_abs_error_pct": round(bbox_max_abs, 6),
                        "volume_pass": abs(volume_error) <= args.volume_threshold_pct,
                        "surface_area_pass": abs(surface_error) <= args.surface_threshold_pct,
                        "bbox_pass": bbox_max_abs <= args.bbox_threshold_pct,
                        "geometry_pass": (
                            abs(volume_error) <= args.volume_threshold_pct
                            and abs(surface_error) <= args.surface_threshold_pct
                            and bbox_max_abs <= args.bbox_threshold_pct
                        ),
                    }
                )
            except Exception as exc:
                row.update(
                    {
                        "evaluation_status": "EVAL_FAIL",
                        "evaluation_error_type": type(exc).__name__,
                        "evaluation_error": str(exc),
                    }
                )
        rows.append(row)
        print(f"{case_id}: {row['evaluation_status']}", flush=True)

    measured = [row for row in rows if row["evaluation_status"] == "MEASURED"]
    volume_errors = [float(row["volume_abs_error_pct"]) for row in measured]
    surface_errors = [float(row["surface_area_abs_error_pct"]) for row in measured]
    bbox_errors = [float(row["bbox_max_abs_error_pct"]) for row in measured]
    status_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["generation_status"])
        status_counts[key] = status_counts.get(key, 0) + 1
    summary: dict[str, object] = {
        "schema_version": 1,
        "manifest": str(manifest_path),
        "generation_dir": str(generation_dir),
        "sample_count": len(rows),
        "generation_status_counts": status_counts,
        "step_export_rate_pct": round(len(measured) / len(rows) * 100.0, 6),
        "measured_count": len(measured),
        "evaluation_failure_count": sum(row["evaluation_status"] == "EVAL_FAIL" for row in rows),
        "thresholds_pct": {
            "volume_abs": args.volume_threshold_pct,
            "surface_area_abs": args.surface_threshold_pct,
            "bbox_axis_max_abs": args.bbox_threshold_pct,
        },
        "volume_abs_error_pct": describe(volume_errors),
        "surface_area_abs_error_pct": describe(surface_errors),
        "bbox_max_abs_error_pct": describe(bbox_errors),
        "volume_pass_count": sum(bool(row.get("volume_pass")) for row in measured),
        "geometry_pass_count": sum(bool(row.get("geometry_pass")) for row in measured),
    }
    batch_summary_path = generation_dir / "batch_summary.json"
    if batch_summary_path.is_file():
        batch_summary = json.loads(batch_summary_path.read_text(encoding="utf-8"))
        summary["model"] = batch_summary.get("model")
    else:
        for row in rows:
            result_path = generation_dir / str(row["id"]) / "result.json"
            if result_path.is_file():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if result.get("model"):
                    summary["model"] = result["model"]
                    break

    evaluation = {"summary": summary, "samples": rows}
    write_json(generation_dir / "evaluation.json", evaluation)
    csv_columns = [
        "id",
        "name",
        "generation_status",
        "evaluation_status",
        "volume_error_pct",
        "volume_abs_error_pct",
        "surface_area_error_pct",
        "surface_area_abs_error_pct",
        "bbox_max_abs_error_pct",
        "volume_pass",
        "surface_area_pass",
        "bbox_pass",
        "geometry_pass",
        "predicted_step",
    ]
    with (generation_dir / "evaluation.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
