"""Cross-validator — re-extracts failed records using a fallback model."""

import json
import os

from ingest.llm_client import chat_json
from ingest.schemas import PageMarkdown
from ingest.validator import validate_param

# Sprint 1 fallback: use qwen-max (same vendor) if MOONSHOT_API_KEY not set
# Long-term: configure MOONSHOT_API_KEY for cross-vendor (kimi-k2.5) validation
_DEFAULT_FALLBACK_MODEL = "qwen3-max-2026-01-23"

SYSTEM_PROMPT = """你是金属切削工艺参数提取器（精确模式）。从以下 Markdown 表格中重新提取参数记录。
严格遵守字段要求:
- table_ref: 必须填写，用表格编号（如"表4-15"）或页码格式"P{N}"（不得为空或"未标注"）
- source_page: 必须为正整数
- value: 仅数字或范围（不含单位）
- unit: 单位字符串

返回 JSON: {"params": [...], "source_page": N}"""


def cross_validate(page: PageMarkdown, raw: dict, client,
                   fallback_model: str = None) -> tuple[bool, any]:
    """
    交叉验证：换模型重新提取，返回 (success, validated_record_or_error)。

    If MOONSHOT_API_KEY is not set, falls back to qwen-max (single-vendor fallback).
    """
    if fallback_model is None:
        if os.environ.get("MOONSHOT_API_KEY"):
            # TODO Sprint 2: implement kimi-k2.5 cross-vendor validation
            fallback_model = _DEFAULT_FALLBACK_MODEL
        else:
            fallback_model = _DEFAULT_FALLBACK_MODEL

    user_content = (
        f"--- Page {page.page_num} ---\n{page.markdown_text}\n\n"
        f"原始提取（包含错误）: {json.dumps(raw, ensure_ascii=False)}"
    )
    try:
        result = chat_json(client, fallback_model, SYSTEM_PROMPT, user_content, max_tokens=4096)
        params = result.get("params", [])
        source_page = result.get("source_page", page.page_num)
        for p in params:
            p["source_page"] = source_page
            if not p.get("table_ref", "").strip() or p.get("table_ref") in ("未标注", "无"):
                p["table_ref"] = f"P{source_page}"
            conditions = p.get("conditions", {})
            if isinstance(conditions, dict):
                p["conditions"] = json.dumps(conditions, ensure_ascii=False)
            elif not isinstance(conditions, str):
                p["conditions"] = "{}"
        # Take first validated param from re-extraction
        for p in params:
            ok, validated = validate_param(p)
            if ok:
                validated.cross_validated = 1
                return True, validated
        return False, "cross_validate: no valid params after re-extraction"
    except Exception as e:
        return False, f"cross_validate failed: {e}"
