#!/usr/bin/env python3
"""Run VLM extraction for prose principle records on rendered source PDF pages."""

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

from experiments.prose_principle_extraction.src.schema import (  # noqa: E402
    validate_principle_payload,
)


DASHSCOPE_BASE = "https://coding.dashscope.aliyuncs.com/v1"
REPO_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_ENV_FILE = Path("/opt/ai-stack/compose/.env")
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = EXPERIMENT_ROOT / "prompts" / "prose_principle_vlm_prompt.md"
IMAGE_DIR = REPO_ROOT / "experiments" / "vlm_source_pdf_process_cards" / "fixtures" / "page_images"
OUTPUT_DIR = EXPERIMENT_ROOT / "output"


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def extract_page(client: OpenAI, model: str, page: int, image_path: Path, prompt: str) -> dict:
    image_url = f"data:image/png;base64,{encode_image(image_path)}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": f"Source PDF page number: {page}\n\n{prompt}"},
                ],
            }
        ],
        response_format={"type": "json_object"},
        max_tokens=8192,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, nargs="+", default=[107])
    parser.add_argument("--model", default=None)
    parser.add_argument("--config", type=Path, default=REPO_CONFIG)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--image-dir", type=Path, default=IMAGE_DIR)
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
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

    base_url = llm_config.get("base_url") or DASHSCOPE_BASE
    model = args.model or llm_config.get("model") or "qwen3.5-plus"

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=300)
    args.out.mkdir(parents=True, exist_ok=True)

    failures = 0
    for page in args.pages:
        image_path = args.image_dir / f"page_{page}.png"
        if not image_path.exists():
            print(f"missing rendered page image: {image_path}")
            failures += 1
            continue
        payload = extract_page(client, model, page, image_path, prompt)
        payload.setdefault("source_page", page)
        errors = validate_principle_payload(payload)
        out_path = args.out / f"principles_page_{page}.json"
        out_path.write_text(
            json.dumps({"payload": payload, "validation_errors": errors}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{page}: errors={len(errors)} path={out_path}")
        if errors:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
