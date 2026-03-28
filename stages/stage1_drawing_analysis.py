"""
Stage 1: Drawing Analysis -- VLM-based engineering drawing feature extraction

Reads an engineering drawing image, sends it to a Vision Language Model
(DashScope OpenAI-compatible API), and extracts structured part features as JSON.
"""

import base64
import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

STAGE_NAME = "Stage1_DrawingAnalysis"

# The expected keys in the output dict -- used for fallback/partial results
EXPECTED_KEYS = [
    "part_type",
    "main_dimensions",
    "surface_finish",
    "geometric_tolerances",
    "features",
    "technical_requirements",
    "material",
]

VLM_SYSTEM_PROMPT = """你是一位拥有20年经验的资深机械工程师，擅长阅读和分析工程图纸。
请严格按照 JSON 格式输出以下字段的分析结果，不要输出任何其他内容。

要求输出的 JSON 结构：
{
  "part_type": "零件类型（如：轴类、盘类、箱体类、支架类、齿轮类等）",
  "main_dimensions": {
    "overall": "总体尺寸描述（长x宽x高 或 直径x长度，含单位mm）",
    "key_dimensions": ["关键尺寸1（含公差）", "关键尺寸2（含公差）", "..."]
  },
  "surface_finish": [
    {"surface": "表面位置描述", "Ra": "粗糙度值（如 Ra1.6）", "method": "加工方法（如有标注）"}
  ],
  "geometric_tolerances": [
    {"type": "公差类型（如：同轴度、圆跳动、平面度、平行度等）", "value": "公差值", "datum": "基准（如有）", "target": "被约束的特征"}
  ],
  "features": [
    {"name": "特征名称（如：通孔、螺纹孔、键槽、倒角、退刀槽等）", "specification": "规格描述", "quantity": "数量"}
  ],
  "technical_requirements": ["技术要求1", "技术要求2"],
  "material": "材料牌号（如：45钢、Q235、HT250、2A12等）"
}

注意事项：
1. 所有尺寸必须包含单位（mm）
2. 公差用标准写法（如 φ50±0.02 或 φ50H7）
3. 如果图纸中某项信息不清晰或未标注，对应字段填写 "未标注" 或空列表
4. 仅输出 JSON，不要添加 markdown 代码块标记或任何说明文字"""

VLM_USER_PROMPT = """请仔细分析这张工程图纸，提取所有零件特征信息，严格按照系统提示中要求的 JSON 格式输出。"""


def _encode_image(image_path: str) -> tuple[str, str]:
    """Read image file and return (base64_data, mime_type)."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(suffix, "image/png")

    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    return b64, mime_type


def _empty_result() -> dict:
    """Return a result dict with all expected keys set to safe defaults."""
    return {
        "part_type": "unknown",
        "main_dimensions": {},
        "surface_finish": [],
        "geometric_tolerances": [],
        "features": [],
        "technical_requirements": [],
        "material": "unknown",
    }


def _parse_vlm_response(raw_text: str) -> dict:
    """
    Try to parse JSON from VLM response.
    Falls back to regex extraction if strict JSON parse fails.
    """
    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Attempt 1: direct JSON parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Attempt 2: find the first {...} block via greedy match
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Attempt 3: regex extraction for individual fields
    result = _empty_result()

    # Try to extract part_type
    pt_match = re.search(r'"part_type"\s*:\s*"([^"]+)"', raw_text)
    if pt_match:
        result["part_type"] = pt_match.group(1)

    # Try to extract material
    mat_match = re.search(r'"material"\s*:\s*"([^"]+)"', raw_text)
    if mat_match:
        result["material"] = mat_match.group(1)

    # Try to extract technical_requirements as a list of strings
    tr_match = re.search(
        r'"technical_requirements"\s*:\s*\[(.*?)\]', raw_text, re.DOTALL
    )
    if tr_match:
        items = re.findall(r'"([^"]+)"', tr_match.group(1))
        if items:
            result["technical_requirements"] = items

    return result


def analyze_drawing(image_path: str, config: dict, tracer: Any) -> dict:
    """
    Analyze an engineering drawing image using a VLM and extract structured part features.

    Args:
        image_path: Path to engineering drawing image (PNG/JPG)
        config: dict with keys llm.base_url, llm.api_key, llm.model, llm.max_tokens, llm.temperature
        tracer: PipelineTracer instance

    Returns:
        dict with keys: part_type, main_dimensions, surface_finish,
        geometric_tolerances, features, technical_requirements, material
    """
    tracer.begin_stage(STAGE_NAME, input_data={"image_path": image_path})

    llm_cfg = config.get("llm", {})
    base_url = llm_cfg.get("base_url", "")
    api_key = llm_cfg.get("api_key", "")
    model = llm_cfg.get("model", "qwen-vl-max")
    max_tokens = llm_cfg.get("max_tokens", 8192)
    temperature = llm_cfg.get("temperature", 0.3)

    # --- Encode image ---
    try:
        b64_data, mime_type = _encode_image(image_path)
        tracer.log_reasoning(
            f"Image loaded: {image_path} ({len(b64_data)} base64 chars, {mime_type})"
        )
    except FileNotFoundError as exc:
        error_msg = f"Image file not found: {exc}"
        tracer.log_error(error_msg)
        result = _empty_result()
        result["_error"] = error_msg
        tracer.end_stage(output_data=result)
        return result
    except Exception as exc:
        error_msg = f"Failed to read image: {exc}"
        tracer.log_error(error_msg)
        result = _empty_result()
        result["_error"] = error_msg
        tracer.end_stage(output_data=result)
        return result

    # --- Build VLM request ---
    image_url = f"data:{mime_type};base64,{b64_data}"

    messages = [
        {"role": "system", "content": VLM_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
                {
                    "type": "text",
                    "text": VLM_USER_PROMPT,
                },
            ],
        },
    ]

    tracer.log_reasoning(
        f"VLM request: model={model}, max_tokens={max_tokens}, temperature={temperature}"
    )

    # --- Call VLM ---
    raw_response_text = ""
    try:
        vlm_timeout = llm_cfg.get("vlm_timeout", 300)
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=vlm_timeout)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        raw_response_text = response.choices[0].message.content or ""
        tracer.log_reasoning(
            f"VLM response received: {len(raw_response_text)} chars. "
            f"Excerpt: {raw_response_text[:300]}..."
        )
    except Exception as exc:
        error_msg = f"VLM API call failed: {type(exc).__name__}: {exc}"
        tracer.log_error(error_msg)
        result = _empty_result()
        result["_error"] = error_msg
        tracer.end_stage(output_data=result)
        return result

    # --- Parse response ---
    try:
        parsed = _parse_vlm_response(raw_response_text)
        # Ensure all expected keys exist
        result = _empty_result()
        for key in EXPECTED_KEYS:
            if key in parsed:
                result[key] = parsed[key]
        tracer.log_reasoning(
            f"Parsed features: part_type={result.get('part_type')}, "
            f"material={result.get('material')}, "
            f"features_count={len(result.get('features', []))}"
        )
    except Exception as exc:
        error_msg = f"Response parsing failed: {type(exc).__name__}: {exc}"
        tracer.log_error(error_msg)
        result = _empty_result()
        result["_error"] = error_msg
        result["_raw_response"] = raw_response_text[:2000]

    tracer.end_stage(output_data=result)
    return result
