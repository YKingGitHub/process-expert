#!/usr/bin/env python3
"""Report whether the View Agent inference and CAD environments are ready."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
from pathlib import Path


DEFAULT_MODEL = Path(
    os.environ.get(
        "VIEW_AGENT_MODEL",
        "/hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-8B-Instruct",
    )
)
DEFAULT_CAD_PYTHON = Path(
    os.environ.get(
        "VIEW_AGENT_CAD_PYTHON",
        "/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python",
    )
)


def package_version(name: str) -> str | None:
    if importlib.util.find_spec(name) is None:
        return None
    module = __import__(name)
    return getattr(module, "__version__", "installed")


def model_files(model_dir: Path) -> dict[str, object]:
    required = {
        "config.json",
        "preprocessor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
    }
    index_path = model_dir / "model.safetensors.index.json"
    if index_path.is_file():
        required.add(index_path.name)
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            required.update(index.get("weight_map", {}).values())
        except (json.JSONDecodeError, OSError):
            pass
    else:
        required.add("model.safetensors")
    missing = sorted(name for name in required if not (model_dir / name).is_file())
    incomplete = [
        name
        for name in sorted(required)
        if Path(str(model_dir / name) + ".aria2").exists()
    ]
    return {
        "path": str(model_dir),
        "exists": model_dir.is_dir(),
        "complete": not missing and not incomplete,
        "missing": missing,
        "incomplete": incomplete,
    }


def cadquery_version(python: Path) -> str | None:
    if not python.is_file():
        return None
    completed = subprocess.run(
        [str(python), "-c", "import cadquery; print(cadquery.__version__)"],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def collect(model_dir: Path, cad_python: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "python": os.sys.version.split()[0],
        "packages": {
            name: package_version(name)
            for name in ("torch", "transformers", "accelerate")
        },
        "model": model_files(model_dir),
        "cad_executor": {
            "python": str(cad_python),
            "cadquery": cadquery_version(cad_python),
        },
    }
    if importlib.util.find_spec("torch") is None:
        result["cuda"] = {"available": False, "device": None}
    else:
        import torch

        available = torch.cuda.is_available()
        result["cuda"] = {
            "available": available,
            "device": torch.cuda.get_device_name(0) if available else None,
            "memory_gib": (
                round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2)
                if available
                else None
            ),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--cad-python", type=Path, default=DEFAULT_CAD_PYTHON)
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()

    # Do not resolve the interpreter symlink: a venv is selected by the invoked
    # path, while the resolved base interpreter does not see the venv packages.
    cad_python = Path(os.path.abspath(args.cad_python.expanduser()))
    result = collect(args.model.resolve(), cad_python)
    packages = result["packages"]
    model = result["model"]
    cuda = result["cuda"]
    ready = bool(
        packages["torch"]
        and packages["transformers"]
        and model["complete"]
        and (not args.require_cuda or cuda["available"])
    )
    result["inference_ready"] = ready
    result["step_export_ready"] = bool(result["cad_executor"]["cadquery"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
