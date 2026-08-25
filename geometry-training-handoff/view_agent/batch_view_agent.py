#!/usr/bin/env python3
"""Run View Agent inference over an input-only manifest with one model load."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from view_agent import (
    DEFAULT_CAD_PYTHON,
    DEFAULT_MODEL,
    PROMPT,
    extract_python,
    generate_code,
    load_model,
    repair_prompt,
    run_executor,
)


TERMINAL_STATUSES = {"STEP_EXPORTED", "CAD_FAIL", "TECH_FAIL"}


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def assert_input_only(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.casefold()
            if "ground_truth" in lowered or lowered == "source_step_archive_path":
                raise ValueError(f"inference manifest contains forbidden evaluation key: {key}")
            assert_input_only(child)
    elif isinstance(value, list):
        for child in value:
            assert_input_only(child)


def load_completed(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return result if result.get("status") in TERMINAL_STATUSES else None


def summarize(output_dir: Path, samples: list[dict[str, object]], started: float) -> dict[str, object]:
    results: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    for sample in samples:
        result_path = output_dir / str(sample["id"]) / "result.json"
        if result_path.is_file():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                result = {"id": sample["id"], "status": "INVALID_RESULT"}
        else:
            result = {"id": sample["id"], "status": "NOT_RUN"}
        status = str(result.get("status", "UNKNOWN"))
        status_counts[status] = status_counts.get(status, 0) + 1
        results.append(
            {
                "id": sample["id"],
                "name": sample["name"],
                "status": status,
                "elapsed_seconds": result.get("elapsed_seconds"),
                "result": str(result_path.resolve()),
            }
        )
    return {
        "sample_count": len(samples),
        "status_counts": status_counts,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cad-python", default=DEFAULT_CAD_PYTHON)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    parser.add_argument("--no-repeat-ngram-size", type=int, default=16)
    parser.add_argument("--min-pixels", type=int, default=256 * 28 * 28)
    parser.add_argument("--max-pixels", type=int, default=1280 * 28 * 28)
    parser.add_argument("--attention", choices=("sdpa", "flash_attention_2"), default="sdpa")
    parser.add_argument("--cad-timeout", type=int, default=120)
    parser.add_argument("--repair-attempts", type=int, default=1)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    args = parser.parse_args()
    if args.repair_attempts < 0:
        parser.error("--repair-attempts must be non-negative")
    if args.shard_count < 1:
        parser.error("--shard-count must be positive")
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("--shard-index must be in [0, shard-count)")

    manifest_path = args.manifest.resolve()
    output_dir = args.output_dir.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("purpose") != "model_input_only_no_ground_truth":
        raise ValueError("refusing a manifest that is not marked input-only")
    assert_input_only(manifest)
    all_samples = manifest.get("samples")
    if not isinstance(all_samples, list) or not all_samples:
        raise ValueError("manifest contains no samples")
    samples = [
        sample
        for sample_index, sample in enumerate(all_samples)
        if sample_index % args.shard_count == args.shard_index
    ]
    if not samples:
        raise ValueError("selected shard contains no samples")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = (
        output_dir / "batch_summary.json"
        if args.shard_count == 1
        else output_dir / f"batch_summary.shard_{args.shard_index:02d}.json"
    )

    started = time.monotonic()
    load_started = time.monotonic()
    model, processor = load_model(args.model, args.attention, args.min_pixels, args.max_pixels)
    model_load_seconds = round(time.monotonic() - load_started, 3)
    print(f"model loaded in {model_load_seconds:.3f}s; samples={len(samples)}", flush=True)

    inferred_count = 0
    for sample_number, sample in enumerate(samples, start=1):
        case_id = str(sample["id"])
        case_dir = output_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        result_path = case_dir / "result.json"
        completed = load_completed(result_path) if args.resume else None
        if completed and not (args.retry_failures and completed.get("status") != "STEP_EXPORTED"):
            print(
                f"[{sample_number:02d}/{len(samples)}] {case_id} resume {completed['status']}",
                flush=True,
            )
            continue

        image_paths = [Path(value).resolve() for value in sample.get("images", [])]
        if not image_paths or any(not path.is_file() for path in image_paths):
            missing = [str(path) for path in image_paths if not path.is_file()]
            result = {
                "id": case_id,
                "name": sample.get("name"),
                "status": "TECH_FAIL",
                "images": [str(path) for path in image_paths],
                "error_type": "MissingInput",
                "error": f"missing drawing images: {missing}" if missing else "no drawing images",
                "attempts": [],
                "elapsed_seconds": 0.0,
            }
            write_json(result_path, result)
            continue

        sample_started = time.monotonic()
        result: dict[str, object] = {
            "id": case_id,
            "name": sample.get("name"),
            "status": "TECH_FAIL",
            "images": [str(path) for path in image_paths],
            "model": args.model,
            "model_role": (
                "base_smoke" if Path(args.model).name.startswith("Qwen3-VL-") else "checkpoint"
            ),
            "prompt": PROMPT,
            "artifacts": {},
            "attempts": [],
        }
        try:
            prompt = PROMPT
            for attempt_index in range(args.repair_attempts + 1):
                raw, telemetry = generate_code(
                    model,
                    processor,
                    image_paths,
                    prompt,
                    args.max_new_tokens,
                    args.repetition_penalty,
                    args.no_repeat_ngram_size,
                )
                if inferred_count == 0 and attempt_index == 0:
                    telemetry["model_load_seconds"] = model_load_seconds
                code = extract_python(raw)
                code_name = (
                    "generated_cadquery.py"
                    if attempt_index == 0
                    else f"generated_cadquery_repair_{attempt_index}.py"
                )
                code_path = case_dir / code_name
                code_path.write_text(code, encoding="utf-8")
                attempt: dict[str, object] = {
                    "index": attempt_index,
                    "cadquery": str(code_path.resolve()),
                    "telemetry": telemetry,
                }
                result["attempts"].append(attempt)
                result["telemetry"] = telemetry
                result["status"] = "CODE_GENERATED"
                result["artifacts"] = {"cadquery": str(code_path.resolve())}
                step_path = case_dir / "generated.step"
                execution = run_executor(args.cad_python, code_path, step_path, args.cad_timeout)
                attempt["execution"] = execution
                result["execution"] = execution
                if execution.get("ok"):
                    result["status"] = "STEP_EXPORTED"
                    result["artifacts"]["step"] = str(step_path.resolve())
                    break
                result["status"] = "CAD_FAIL"
                prompt = repair_prompt(code, execution)
            inferred_count += 1
        except Exception as exc:
            result["status"] = "TECH_FAIL"
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc)
        result["elapsed_seconds"] = round(time.monotonic() - sample_started, 3)
        write_json(result_path, result)
        summary = summarize(output_dir, samples, started)
        summary.update({"model": args.model, "manifest": str(manifest_path)})
        summary.update(
            {
                "shard_count": args.shard_count,
                "shard_index": args.shard_index,
                "total_manifest_sample_count": len(all_samples),
            }
        )
        write_json(summary_path, summary)
        print(
            f"[{sample_number:02d}/{len(samples)}] {case_id} {result['status']} "
            f"{result['elapsed_seconds']}s",
            flush=True,
        )

    summary = summarize(output_dir, samples, started)
    summary.update(
        {
            "model": args.model,
            "manifest": str(manifest_path),
            "model_load_seconds": model_load_seconds,
            "shard_count": args.shard_count,
            "shard_index": args.shard_index,
            "total_manifest_sample_count": len(all_samples),
        }
    )
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
