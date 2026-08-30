"""
Stage 2: Web Research -- 工艺路线框架检索

Given a part_type and material from Stage 1:
1. Use DuckDuckGo to search for real machining process information
2. Feed search results into an LLM to synthesize a structured process framework

If web search or LLM fails, a pre-built generic framework is returned as fallback.
"""

import json
import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import duckduckgo_search; if unavailable, web search is skipped
# ---------------------------------------------------------------------------
try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    logger.warning("duckduckgo-search not installed; web search will be skipped")

# ---------------------------------------------------------------------------
# Fallback framework -- covers most rotational/machining part scenarios
# ---------------------------------------------------------------------------

GENERIC_ROTATIONAL_FRAMEWORK: dict[str, Any] = {
    "typical_sequence": [
        {"op_name": "领料", "key_points": ["核对材料牌号", "检查毛坯尺寸"], "equipment_type": "无"},
        {"op_name": "粗车", "key_points": ["三爪夹持", "车外圆", "留余量"], "equipment_type": "车床"},
        {"op_name": "精车", "key_points": ["软爪夹持", "控制公差", "表面粗糙度"], "equipment_type": "数控车床"},
        {"op_name": "铣削", "key_points": ["分中找正", "铣特征", "形位公差"], "equipment_type": "加工中心"},
        {"op_name": "去毛刺/标识", "key_points": ["去毛刺", "打标"], "equipment_type": "打标机"},
        {"op_name": "检验", "key_points": ["尺寸检验", "形位公差", "表面质量"], "equipment_type": "无"},
        {"op_name": "入库", "key_points": ["清洗", "包装"], "equipment_type": "无"},
    ],
    "quality_notes": [
        "不锈钢加工注意排屑",
        "薄壁件注意装夹变形",
        "焊接件注意应力消除",
    ],
}


# ---------------------------------------------------------------------------
# Web search via DuckDuckGo
# ---------------------------------------------------------------------------

def _build_search_queries(part_type: str, material: str) -> list[str]:
    """Build diverse queries for web search."""
    queries = [
        f"{part_type} {material} 加工工艺路线 工序",
        f"{part_type} 机加工 工艺卡 工序编排",
    ]
    # Add material-specific query if material is provided
    if material and material != "未标注":
        queries.append(f"{material} 切削参数 加工性能 注意事项")
    return queries


def _web_search(queries: list[str], tracer, timeout: int = 15) -> list[dict]:
    """
    Execute DuckDuckGo searches and return aggregated results.

    Returns list of {"title": str, "body": str, "href": str} dicts.
    """
    if not HAS_DDGS:
        tracer.log_reasoning("duckduckgo-search package not available; skipping web search")
        return []

    all_results = []
    seen_urls = set()

    for query in queries:
        try:
            tracer.log_reasoning(f"DuckDuckGo search: '{query}'")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5, region="cn-zh"))

            unique_count = 0
            for r in results:
                url = r.get("href", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "href": url,
                    })
                    unique_count += 1

            tracer.log_search_result(
                source="DuckDuckGo",
                query=query,
                results_summary=f"{len(results)} results, {unique_count} unique new",
            )
        except Exception as exc:
            tracer.log_reasoning(f"DuckDuckGo search failed for '{query}': {exc}")
            tracer.log_search_result(
                source="DuckDuckGo",
                query=query,
                results_summary=f"ERROR: {type(exc).__name__}: {exc}",
            )

    return all_results


# ---------------------------------------------------------------------------
# LLM prompt with web search context
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "你是一名资深机加工工艺工程师。用户会提供零件类型、材料牌号，以及从网络搜索到的参考资料。"
    "请根据你的专业知识和参考资料，描述该零件的典型机加工工艺路线。\n\n"
    "请严格以 JSON 格式输出，不要输出任何其他文字。JSON 结构如下：\n"
    "{\n"
    '  "typical_sequence": [\n'
    '    {"op_name": "工序名称", "key_points": ["要点1", "要点2"], "equipment_type": "设备类型"}\n'
    "  ],\n"
    '  "quality_notes": ["质量注意事项1", "质量注意事项2"]\n'
    "}\n\n"
    "要求：\n"
    "- typical_sequence 按实际加工顺序排列，从领料到入库\n"
    "- 每道工序包含 op_name（工序名）、key_points（关键要点列表）、equipment_type（典型设备）\n"
    "- quality_notes 列出该材料/零件加工的特殊质量注意事项\n"
    "- 仅输出 JSON，不加 markdown 代码块标记"
)


def _build_user_prompt(
    part_type: str,
    material: str,
    web_results: list[dict],
) -> str:
    """Build user prompt incorporating web search results."""
    # Format web results as reference material
    if web_results:
        web_context_parts = []
        for i, r in enumerate(web_results[:10], 1):  # max 10 results
            title = r.get("title", "")
            body = r.get("body", "")
            web_context_parts.append(f"  {i}. {title}\n     {body}")
        web_context = "\n".join(web_context_parts)
        web_section = f"\n网络搜索参考资料:\n{web_context}\n"
    else:
        web_section = "\n(无网络搜索结果，请依据专业知识)\n"

    return (
        f"零件类型: {part_type}\n"
        f"材料牌号: {material}\n"
        f"{web_section}\n"
        f"请给出该零件从毛坯到成品的完整加工工艺路线（JSON 格式）。"
    )


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output that may contain markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Result validation
# ---------------------------------------------------------------------------

def _validate_framework(data: dict) -> bool:
    """Ensure the LLM output has the expected structure."""
    if not isinstance(data, dict):
        return False
    seq = data.get("typical_sequence")
    if not isinstance(seq, list) or len(seq) == 0:
        return False
    for item in seq:
        if not isinstance(item, dict):
            return False
        if "op_name" not in item or "key_points" not in item or "equipment_type" not in item:
            return False
        if not isinstance(item["key_points"], list):
            return False
    if not isinstance(data.get("quality_notes"), list):
        return False
    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def research_process_framework(
    part_type: str,
    material: str,
    config: dict,
    tracer,
) -> dict:
    """
    Query the web + LLM for a typical machining process framework.

    Steps:
      1. DuckDuckGo search for material + part type + machining process info
      2. Feed search results into LLM to synthesize structured framework
      3. Fallback to generic framework if anything fails
    """
    tracer.begin_stage(
        "Stage2_WebResearch",
        {"part_type": part_type, "material": material},
    )

    # --- Check if web search is disabled in config --------------------------
    web_search_enabled = config.get("web_search", {}).get("enabled", True)
    if not web_search_enabled:
        tracer.log_reasoning(
            "web_search.enabled=false in config; skipping web search, "
            "returning generic rotational framework."
        )
        tracer.end_stage(GENERIC_ROTATIONAL_FRAMEWORK)
        return dict(GENERIC_ROTATIONAL_FRAMEWORK)

    # --- Step 1: Web search -------------------------------------------------
    queries = _build_search_queries(part_type, material)
    tracer.log_reasoning(
        f"Search strategy: {len(queries)} queries for "
        f"part_type='{part_type}', material='{material}'"
    )

    web_search_timeout = config.get("web_search", {}).get("timeout", 15)
    web_results = _web_search(queries, tracer, timeout=web_search_timeout)

    tracer.log_reasoning(
        f"Web search complete: {len(web_results)} total unique results"
    )

    # --- Step 2: LLM synthesis ----------------------------------------------
    llm_config = config.get("llm", {})
    base_url = llm_config.get("base_url", "")
    api_key = llm_config.get("api_key", "")
    text_model = llm_config.get("text_model", "qwen3.5-plus")
    max_tokens = llm_config.get("max_tokens", 8192)
    temperature = llm_config.get("temperature", 0.3)
    llm_timeout = config.get("web_search", {}).get("llm_timeout", 120)

    user_prompt = _build_user_prompt(part_type, material, web_results)
    tracer.log_reasoning(
        f"LLM synthesis: model={text_model}, timeout={llm_timeout}s, "
        f"web_results_fed={len(web_results)}"
    )

    try:
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=llm_timeout,
        )

        response = client.chat.completions.create(
            model=text_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        raw_content = response.choices[0].message.content or ""
        tracer.log_reasoning(f"LLM returned {len(raw_content)} chars")

        framework = _extract_json(raw_content)

        if not _validate_framework(framework):
            tracer.log_reasoning(
                "LLM output failed validation; falling back to generic framework."
            )
            tracer.log_error(
                f"Validation failed. Raw output (first 500 chars): "
                f"{raw_content[:500]}"
            )
            framework = dict(GENERIC_ROTATIONAL_FRAMEWORK)
        else:
            tracer.log_reasoning(
                f"LLM output validated: "
                f"{len(framework['typical_sequence'])} operations, "
                f"{len(framework['quality_notes'])} quality notes."
            )

        # Attach web search snippets for downstream stages
        if web_results:
            framework["_web_snippets"] = [
                f"{r['title']}: {r['body']}" for r in web_results[:5]
            ]

    except json.JSONDecodeError as exc:
        logger.warning("Stage2 LLM output not valid JSON: %s", exc)
        tracer.log_error(f"JSON parse error: {exc}")
        tracer.log_reasoning(
            "Failed to parse LLM JSON output; falling back to generic framework."
        )
        framework = dict(GENERIC_ROTATIONAL_FRAMEWORK)

    except Exception as exc:
        err_msg = f"LLM call failed: {type(exc).__name__}: {exc}"
        logger.warning("Stage2 LLM call failed: %s", exc)
        tracer.log_error(err_msg)
        tracer.log_reasoning(
            "LLM call raised an exception; falling back to generic framework."
        )
        framework = dict(GENERIC_ROTATIONAL_FRAMEWORK)

    tracer.end_stage(framework)
    return framework
