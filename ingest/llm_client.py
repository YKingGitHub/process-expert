"""LLM client — DashScope OpenAI-compatible API wrapper."""

import json
import os

from openai import OpenAI

DASHSCOPE_BASE = "https://coding.dashscope.aliyuncs.com/v1"


def get_client() -> OpenAI:
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY not set")
    return OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE)


def chat_json(client: OpenAI, model: str, system: str, user: str,
              max_tokens: int = 4096) -> dict:
    """发起 JSON mode 请求，返回解析后的 dict。失败时抛出异常。"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
        extra_body={"enable_thinking": False},
    )
    return json.loads(resp.choices[0].message.content)
