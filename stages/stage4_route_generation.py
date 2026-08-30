"""
Stage 4 — 工艺路线生成

组装 Stage 1-3 的结果 + 用户输入（毛坯、设备、材料），
调用 LLM 生成完整的结构化工艺路线 JSON。

输出: list[dict]，每个 dict 代表一道工序。
"""

import json
import logging
import re
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context assembly limits (characters)
# ---------------------------------------------------------------------------
LIMIT_STAGE1 = 2000  # part features
LIMIT_STAGE2 = 3000  # process framework
LIMIT_STAGE3 = 3000  # KB params + experience + web results

# Minimum validation thresholds
MIN_OPERATIONS = 6
REQUIRED_OP_TYPES = ["领料", "入库"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _truncate_text(text: str, limit: int) -> str:
    """Truncate text to character limit, appending an ellipsis marker."""
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit] + "...(已截断)"


def _section_to_text(data: Any, limit: int) -> str:
    """Convert a dict/str/list to a readable text block, then truncate."""
    if data is None:
        return ""
    if isinstance(data, str):
        return _truncate_text(data, limit)
    try:
        raw = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        raw = str(data)
    return _truncate_text(raw, limit)


def _truncate_kb_results(kb_results: dict, limit: int) -> str:
    """
    Truncate KB results with priority: params > experience > web_results.

    Each sub-section gets a proportional budget, but lower-priority sections
    yield remaining budget to higher-priority ones.
    """
    params_raw = kb_results.get("params") or kb_results.get("parameters") or ""
    experience_raw = kb_results.get("experience") or kb_results.get("experiences") or ""
    # Combine web results and manual excerpts
    manual_raw = kb_results.get("manual_excerpts") or ""
    web_raw = kb_results.get("web_results") or kb_results.get("web") or ""
    if manual_raw and not web_raw:
        web_raw = manual_raw
    elif manual_raw and web_raw:
        # Merge both into web_raw (lower priority slot)
        if isinstance(manual_raw, list) and isinstance(web_raw, list):
            web_raw = manual_raw + web_raw
        elif isinstance(manual_raw, list):
            web_raw = manual_raw
        # else keep web_raw as is

    # Convert to strings if needed
    if not isinstance(params_raw, str):
        try:
            params_raw = json.dumps(params_raw, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            params_raw = str(params_raw)
    if not isinstance(experience_raw, str):
        try:
            experience_raw = json.dumps(experience_raw, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            experience_raw = str(experience_raw)
    if not isinstance(web_raw, str):
        try:
            web_raw = json.dumps(web_raw, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            web_raw = str(web_raw)

    # Priority allocation: params gets most, web_results gets least
    # Start by giving each a third, then redistribute unused budget
    budget_params = limit // 3
    budget_experience = limit // 3
    budget_web = limit - budget_params - budget_experience

    # First pass: truncate web (lowest priority)
    web_text = _truncate_text(web_raw, budget_web)
    web_saved = budget_web - len(web_text)

    # Redistribute saved budget to experience
    budget_experience += web_saved // 2
    budget_params += web_saved - (web_saved // 2)

    # Second pass: truncate experience
    exp_text = _truncate_text(experience_raw, budget_experience)
    exp_saved = budget_experience - len(exp_text)

    # Redistribute to params (highest priority)
    budget_params += exp_saved

    # Final pass: truncate params
    params_text = _truncate_text(params_raw, budget_params)

    sections = []
    if params_text:
        sections.append(f"【工艺参数】\n{params_text}")
    if exp_text:
        sections.append(f"【工艺经验】\n{exp_text}")
    if web_text:
        sections.append(f"【网络参考】\n{web_text}")

    return "\n\n".join(sections) if sections else "(无知识库结果)"


def _build_prompt(
    part_text: str,
    framework_text: str,
    kb_text: str,
    blank_info: str,
    equipment: str,
    material: str,
) -> str:
    """Construct the Chinese system+user prompt for route generation."""

    system_prompt = (
        "你是一位拥有20年经验的资深工艺工程师，擅长机械加工工艺设计。"
        "请根据提供的零件特征、工艺框架、知识库参数和经验，"
        "生成一条完整、合理、可直接用于生产的工艺路线。"
    )

    user_prompt = f"""## 任务
请为以下零件生成完整的工艺路线。

## 零件特征
{part_text}

## 材料
{material}

## 毛坯信息
{blank_info}

## 可用设备
{equipment}

## 参考工艺框架
{framework_text}

## 知识库参数与经验
{kb_text}

## 输出要求

1. 输出**纯 JSON 数组**，不要添加任何 Markdown 标记或额外文字。
2. 工序数量不少于 6 道，必须包含"领料"和"入库"工序。
3. 工序编号 seq 采用两位字符串，从 "05" 开始，步长 5（如 "05", "10", "15"...）。
4. 每道工序的 JSON 结构如下:

```json
[
  {{
    "seq": "05",
    "op_name": "领料",
    "op_type": "领料",
    "content": ["描述1", "描述2"],
    "equipment": "设备名",
    "tooling": "工装/量具",
    "inspection": "检验要求"
  }}
]
```

5. op_type 常见取值: 领料、车削、铣削、钻孔、磨削、钳工、热处理、检验、入库 等。
6. content 数组中每条描述应具体、可执行，包含尺寸公差和表面粗糙度要求。
7. equipment 填写具体设备型号或类型。
8. tooling 填写所需的刀具、夹具、量具。
9. inspection 填写该工序的检验方法和要求。
10. 工艺路线应遵循合理的加工顺序: 领料 → 粗加工 → 半精加工 → 精加工 → 检验 → 入库。

请直接输出 JSON 数组:"""

    return system_prompt, user_prompt


def _extract_json_from_response(text: str) -> list[dict]:
    """
    Parse JSON from LLM response. If direct parsing fails,
    try extracting from markdown code blocks.
    """
    # First try: direct parse
    stripped = text.strip()
    try:
        result = json.loads(stripped)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Second try: extract from markdown code blocks (```json ... ``` or ``` ... ```)
    patterns = [
        r"```json\s*\n?(.*?)\n?\s*```",
        r"```\s*\n?(.*?)\n?\s*```",
    ]
    for pattern in patterns:
        match = re.search(pattern, stripped, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue

    # Third try: find the first [ ... ] block in the text
    bracket_match = re.search(r"\[.*\]", stripped, re.DOTALL)
    if bracket_match:
        try:
            result = json.loads(bracket_match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse JSON from LLM response. Response starts with: {stripped[:200]}")


def _validate_route(route: list[dict]) -> list[str]:
    """
    Validate the generated route. Returns a list of warning/error messages.
    Raises ValueError if critical validation fails.
    """
    errors = []

    if len(route) < MIN_OPERATIONS:
        errors.append(
            f"工序数量不足: 期望 >= {MIN_OPERATIONS}, 实际 {len(route)}"
        )

    op_types_found = set()
    for step in route:
        op_type = step.get("op_type", "")
        op_types_found.add(op_type)

    for required in REQUIRED_OP_TYPES:
        if required not in op_types_found:
            errors.append(f"缺少必需工序类型: {required}")

    if errors:
        raise ValueError("; ".join(errors))

    return []


def _estimate_tokens(text: str) -> int:
    """
    Rough token estimation for Chinese + mixed text.
    Chinese characters ~= 1-2 tokens each; English words ~= 1 token.
    Use a conservative 1.5 chars per token for mixed content.
    """
    if not text:
        return 0
    return max(1, int(len(text) / 1.5))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_process_route(
    part_features: dict,
    process_framework: dict,
    kb_results: dict,
    blank_info: str,
    equipment: str,
    material: str,
    config: dict,
    tracer,
) -> list[dict]:
    """
    Stage 4: Generate a complete structured process route using an LLM.

    Args:
        part_features: Output from Stage 1 (part feature extraction).
        process_framework: Output from Stage 2 (process framework).
        kb_results: Output from Stage 3 (KB parameters, experience, web results).
        blank_info: User-provided blank/stock info, e.g. "⌀50×100".
        equipment: User-provided available equipment, e.g. "数控车床, 三轴加工中心".
        material: User-provided material info.
        config: Configuration dict (must include 'llm' section).
        tracer: PipelineTracer instance for logging.

    Returns:
        list[dict]: List of process step dicts with keys:
            seq, op_name, op_type, content, equipment, tooling, inspection.

    Raises:
        ValueError: If LLM output cannot be parsed or fails validation.
        Exception: If LLM API call fails.
    """
    tracer.begin_stage(
        "Stage4-RouteGeneration",
        input_data={
            "part_features_keys": list(part_features.keys()) if part_features else [],
            "framework_keys": list(process_framework.keys()) if process_framework else [],
            "kb_keys": list(kb_results.keys()) if kb_results else [],
            "blank_info": blank_info,
            "equipment": equipment,
            "material": material,
        },
    )

    try:
        # ----- 1. Assemble context with truncation -----
        part_text = _section_to_text(part_features, LIMIT_STAGE1)
        framework_text = _section_to_text(process_framework, LIMIT_STAGE2)
        kb_text = _truncate_kb_results(kb_results or {}, LIMIT_STAGE3)

        # Token estimation for logging
        est_part_tokens = _estimate_tokens(part_text)
        est_framework_tokens = _estimate_tokens(framework_text)
        est_kb_tokens = _estimate_tokens(kb_text)
        est_total_context = est_part_tokens + est_framework_tokens + est_kb_tokens

        tracer.log_reasoning(
            f"Context token estimates: "
            f"part={est_part_tokens}, framework={est_framework_tokens}, "
            f"kb={est_kb_tokens}, total_context~={est_total_context}"
        )
        tracer.log_reasoning(
            f"Context char lengths: "
            f"part={len(part_text)}/{LIMIT_STAGE1}, "
            f"framework={len(framework_text)}/{LIMIT_STAGE2}, "
            f"kb={len(kb_text)}/{LIMIT_STAGE3}"
        )

        # ----- 2. Build prompt -----
        llm_config = config.get("llm", {})
        system_prompt, user_prompt = _build_prompt(
            part_text=part_text,
            framework_text=framework_text,
            kb_text=kb_text,
            blank_info=blank_info or "(未提供)",
            equipment=equipment or "(未提供)",
            material=material or "(未提供)",
        )

        est_prompt_tokens = _estimate_tokens(system_prompt + user_prompt)
        max_tokens = llm_config.get("max_tokens", 8192)
        tracer.log_reasoning(
            f"Prompt strategy: system+user ~{est_prompt_tokens} tokens, "
            f"max_tokens={max_tokens}, "
            f"model={llm_config.get('text_model', 'unknown')}"
        )

        # ----- 3. Call LLM -----
        text_timeout = llm_config.get("text_timeout", 120)
        client = OpenAI(
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", ""),
            timeout=text_timeout,
        )

        logger.info(
            "Calling LLM for route generation: model=%s, max_tokens=%d",
            llm_config.get("text_model"),
            max_tokens,
        )

        response = client.chat.completions.create(
            model=llm_config.get("text_model", "qwen3.5-plus"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=llm_config.get("temperature", 0.3),
        )

        raw_content = response.choices[0].message.content or ""
        logger.info("LLM response received: %d chars", len(raw_content))

        # ----- 4. Parse JSON -----
        try:
            route = _extract_json_from_response(raw_content)
        except ValueError as parse_err:
            tracer.log_error(f"JSON parse failed: {parse_err}")
            raise

        tracer.log_reasoning(f"Parsed {len(route)} operations from LLM response")

        # ----- 5. Validate -----
        try:
            _validate_route(route)
        except ValueError as val_err:
            tracer.log_error(f"Route validation failed: {val_err}")
            raise

        op_names = [step.get("op_name", "?") for step in route]
        tracer.log_reasoning(f"Validation passed. Operations: {op_names}")

        # ----- 6. Log output and finish -----
        tracer.end_stage(output_data={
            "operation_count": len(route),
            "operations": op_names,
            "first_op": route[0] if route else None,
            "last_op": route[-1] if route else None,
        })

        return route

    except Exception as exc:
        # Ensure the stage is ended even on failure
        if tracer._current_stage is not None:
            tracer.log_error(str(exc))
            tracer.end_stage(output_data=None)
        raise
