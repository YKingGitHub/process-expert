#!/usr/bin/env python3
"""View Agent: one or more orthographic drawing sheets -> CadQuery -> STEP."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path


DEFAULT_MODEL = os.environ.get(
    "VIEW_AGENT_MODEL",
    "/hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-8B-Instruct",
)
DEFAULT_CAD_PYTHON = os.environ.get(
    "VIEW_AGENT_CAD_PYTHON",
    "/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python",
)
PROMPT = (
    "Generate the CadQuery code needed to create the CAD for the provided "
    "dimensioned orthographic engineering drawing. Use the dimensions shown "
    "in the drawing and treat them as millimetres. Assign the final valid "
    "CadQuery object to the variable "
    "`solid` in the last line. Keep the program concise (under 80 lines), use "
    "named dimensions and intermediate solids, and never repeat an identical "
    "operation. Infer axial topology from section views: an opening that spans "
    "the full section thickness is a through-hole, while a shallow enlarged "
    "opening is a recess or counterbore. Distinguish feature-count prefixes "
    "such as `2-R4` from diameter dimensions; do not use a count as a length or "
    "diameter. Do not physically model tolerances, GD&T frames, surface finish, "
    "or annotation symbols. Do not export, visualize, read files, access "
    "the network, or use any library other than cadquery and math. Return just "
    "the Python code, with no explanation. Use valid CadQuery idioms: create a "
    "cylinder with cq.Workplane('XY').circle(radius).extrude(length); make a "
    "through-hole with .faces('>Z').workplane().hole(diameter); make a recess "
    "with .faces('>Z').workplane().circle(radius).cutBlind(-depth). Never call "
    "extrude on an already-created solid, and only chamfer or fillet selected "
    "edges."
)


def repair_prompt(previous_code: str, execution: dict[str, object]) -> str:
    error = execution.get("error") or execution.get("stderr") or "unknown CAD error"
    return (
        f"{PROMPT}\n\n"
        "The previous answer failed validation or CAD execution. Return a complete "
        "corrected program, not a patch.\n"
        f"Failure: {error}\n"
        "Previous program:\n"
        f"```python\n{previous_code}\n```"
    )


def extract_python(text: str) -> str:
    fenced = re.search(
        r"```(?:python)?\s*(.*?)(?:```|\Z)", text, flags=re.I | re.S
    )
    code = fenced.group(1) if fenced else text
    code = code.strip()
    if not code:
        raise ValueError("model returned empty code")
    return code + "\n"


def load_model(
    model_path: str, attention: str, min_pixels: int, max_pixels: int
):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; run this entrypoint inside a Slurm GPU allocation")
    local_only = Path(model_path).exists()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        attn_implementation=attention,
        local_files_only=local_only,
    ).to("cuda")
    model.eval()
    model.generation_config.temperature = None
    model.generation_config.top_p = None
    model.generation_config.top_k = None
    processor = AutoProcessor.from_pretrained(
        model_path,
        size={"shortest_edge": min_pixels, "longest_edge": max_pixels},
        local_files_only=local_only,
    )
    return model, processor


def build_messages(image_paths: list[Path], prompt: str) -> list[dict[str, object]]:
    if not image_paths:
        raise ValueError("at least one drawing image is required")
    return [
        {
            "role": "user",
            "content": [
                *(
                    {"type": "image", "image": str(image_path)}
                    for image_path in image_paths
                ),
                {"type": "text", "text": prompt},
            ],
        }
    ]


def generate_code(
    model,
    processor,
    image_paths: list[Path],
    prompt: str,
    max_new_tokens: int,
    repetition_penalty: float,
    no_repeat_ngram_size: int,
) -> tuple[str, dict[str, object]]:
    import torch

    messages = build_messages(image_paths, prompt)
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    )
    for key, value in list(inputs.items()):
        if not torch.is_tensor(value):
            continue
        if key in {"pixel_values", "pixel_values_videos"}:
            inputs[key] = value.to("cuda", dtype=torch.bfloat16)
        else:
            inputs[key] = value.to("cuda")

    torch.cuda.reset_peak_memory_stats()
    generation_started = time.monotonic()
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            repetition_penalty=repetition_penalty,
            no_repeat_ngram_size=no_repeat_ngram_size,
            use_cache=True,
        )
    generated = output_ids[:, inputs["input_ids"].shape[1] :]
    text = processor.batch_decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()
    telemetry = {
        "prompt_tokens": int(inputs["input_ids"].shape[1]),
        "generated_tokens": int(generated.shape[1]),
        "generation_seconds": round(time.monotonic() - generation_started, 3),
        "cuda_allocated_gib": round(torch.cuda.memory_allocated() / 2**30, 3),
        "cuda_peak_allocated_gib": round(
            torch.cuda.max_memory_allocated() / 2**30, 3
        ),
    }
    return text, telemetry


def run_executor(
    cad_python: str, code_path: Path, step_path: Path, timeout: int
) -> dict[str, object]:
    cache_dir = step_path.parent / f".view-agent-cache-{os.getuid()}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.setdefault("XDG_CACHE_HOME", str(cache_dir))
    command = [
        cad_python,
        "-I",
        str(Path(__file__).with_name("cad_executor.py")),
        "--code",
        str(code_path),
        "--step",
        str(step_path),
    ]
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return {
            "returncode": None,
            "ok": False,
            "error_type": "TimeoutExpired",
            "error": f"CAD execution exceeded {timeout} seconds",
        }
    payload = completed.stdout.strip().splitlines()
    result: dict[str, object] = {
        "returncode": completed.returncode,
        "stderr": completed.stderr[-2000:],
    }
    if payload:
        try:
            result.update(json.loads(payload[-1]))
        except json.JSONDecodeError:
            result["stdout"] = completed.stdout[-2000:]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        type=Path,
        action="append",
        required=True,
        help="drawing sheet; repeat for a multi-sheet part",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cad-python", default=DEFAULT_CAD_PYTHON)
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    parser.add_argument("--no-repeat-ngram-size", type=int, default=16)
    parser.add_argument("--min-pixels", type=int, default=256 * 28 * 28)
    parser.add_argument("--max-pixels", type=int, default=1280 * 28 * 28)
    parser.add_argument("--attention", choices=("sdpa", "flash_attention_2"), default="sdpa")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cad-timeout", type=int, default=120)
    parser.add_argument("--repair-attempts", type=int, default=1)
    args = parser.parse_args()
    if args.repair_attempts < 0:
        parser.error("--repair-attempts must be non-negative")

    image_paths = [image.resolve() for image in args.image]
    output_dir = args.output_dir.resolve()
    for image_path in image_paths:
        if not image_path.is_file():
            parser.error(f"image does not exist: {image_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    step_path = output_dir / "generated.step"
    result: dict[str, object] = {
        "status": "TECH_FAIL",
        "images": [str(image_path) for image_path in image_paths],
        "model": args.model,
        "model_role": (
            "base_smoke"
            if Path(args.model).name.startswith("Qwen3-VL-")
            else "checkpoint"
        ),
        "prompt": PROMPT,
        "artifacts": {},
        "attempts": [],
    }

    started = time.monotonic()
    try:
        load_started = time.monotonic()
        model, processor = load_model(
            args.model, args.attention, args.min_pixels, args.max_pixels
        )
        model_load_seconds = round(time.monotonic() - load_started, 3)
        prompt = PROMPT
        attempt_count = args.repair_attempts + 1 if args.execute else 1
        for attempt_index in range(attempt_count):
            raw, telemetry = generate_code(
                model,
                processor,
                image_paths,
                prompt,
                args.max_new_tokens,
                args.repetition_penalty,
                args.no_repeat_ngram_size,
            )
            if attempt_index == 0:
                telemetry["model_load_seconds"] = model_load_seconds
            code = extract_python(raw)
            code_name = (
                "generated_cadquery.py"
                if attempt_index == 0
                else f"generated_cadquery_repair_{attempt_index}.py"
            )
            code_path = output_dir / code_name
            code_path.write_text(code, encoding="utf-8")
            attempt: dict[str, object] = {
                "index": attempt_index,
                "cadquery": str(code_path),
                "telemetry": telemetry,
            }
            result["attempts"].append(attempt)
            result["telemetry"] = telemetry
            result["status"] = "CODE_GENERATED"
            result["artifacts"] = {"cadquery": str(code_path)}
            if not args.execute:
                break
            execution = run_executor(
                args.cad_python, code_path, step_path, args.cad_timeout
            )
            attempt["execution"] = execution
            result["execution"] = execution
            if execution.get("ok"):
                result["status"] = "STEP_EXPORTED"
                result["artifacts"]["step"] = str(step_path)
                break
            result["status"] = "CAD_FAIL"
            prompt = repair_prompt(code, execution)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == ("STEP_EXPORTED" if args.execute else "CODE_GENERATED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
