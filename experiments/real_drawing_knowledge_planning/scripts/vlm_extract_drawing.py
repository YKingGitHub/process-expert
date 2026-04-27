#!/usr/bin/env python3
"""Run VLM extraction on the real drawing PNG test file."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import yaml
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from experiments.real_drawing_knowledge_planning.src.schema import (  # noqa: E402
    validate_drawing_analysis,
)


DASHSCOPE_BASE = "https://coding.dashscope.aliyuncs.com/v1"
DEFAULT_ENV_FILE = Path("/opt/ai-stack/compose/.env")
REPO_CONFIG = REPO_ROOT / "config.yaml"
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = EXPERIMENT_ROOT / "prompts" / "drawing_vlm_prompt.md"
DEFAULT_IMAGE = Path("test-files/测试.png")
OUTPUT_PATH = EXPERIMENT_ROOT / "fixtures" / "drawing_analysis.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--model", default=None)
    parser.add_argument("--config", type=Path, default=REPO_CONFIG)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    args = parser.parse_args()

    llm_config = load_llm_config(args.config)
    api_key = (
        os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("DASHSCOPE_CODING_API_KEY")
        or load_env_key(args.env_file)
        or llm_config.get("api_key")
    )
    if not api_key:
        raise SystemExit("No API key found in DASHSCOPE_API_KEY, DASHSCOPE_CODING_API_KEY, or config.yaml llm.api_key")

    client = OpenAI(api_key=api_key, base_url=llm_config.get("base_url") or DASHSCOPE_BASE, timeout=300)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = extract_drawing(client, args.model or llm_config.get("model") or "qwen3.5-plus", args.image, prompt)
    if not payload.get("source_file"):
        payload["source_file"] = str(args.image)
    if not payload.get("extraction_mode"):
        payload["extraction_mode"] = "drawing_png_vlm"
    errors = validate_drawing_analysis(payload)
    if errors:
        raise SystemExit(json.dumps({"validation_errors": errors}, ensure_ascii=False, indent=2))
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "dimensions": len(payload["dimensions"]), "features": len(payload["features"])}, ensure_ascii=False, indent=2))
    return 0


def extract_drawing(client: OpenAI, model: str, image_path: Path, prompt: str) -> dict:
    image_url = f"data:image/png;base64,{base64.b64encode(image_path.read_bytes()).decode('utf-8')}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        response_format={"type": "json_object"},
        max_tokens=16384,
        extra_body={"enable_thinking": False},
    )
    return json.loads(resp.choices[0].message.content)


def load_llm_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data.get("llm", {}) or {}


def load_env_key(env_file: Path) -> str | None:
    if not env_file.exists():
        return None
    for line in env_file.read_text(errors="ignore").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "DASHSCOPE_API_KEY":
            return value.strip().strip("\"'")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
