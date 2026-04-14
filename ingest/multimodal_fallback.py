"""VLM multimodal fallback — handles pages that fail Tier 1 + Tier 2 extraction."""

import base64
import json
import time

import fitz  # PyMuPDF
from pydantic import ValidationError

from ingest.schemas import ProcessParam


class VLMFallback:
    """Tier 3 fallback: renders a PDF page to PNG and uses qwen3.5-plus VLM to extract params."""

    def __init__(self, client, model: str = "qwen3.5-plus"):
        self.client = client
        self.model = model

    def render_page_image(self, fitz_page) -> str:
        """渲染页面为 base64 PNG（2x 缩放保证清晰度）"""
        mat = fitz.Matrix(2, 2)
        pix = fitz_page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        return base64.b64encode(img_bytes).decode("utf-8")

    def extract_with_vlm(self, fitz_page, page_num: int, page_type: str,
                         max_retries: int = 2) -> list:
        """VLM 多模态提取：返回校验通过的记录列表，失败（含 API 异常）返回空列表。

        含重试逻辑（最多 2 次，指数退避 1s/2s）。
        注意：对 knowledge_table 类型，仅尝试提取 ProcessParam 格式参数；
        若页面无参数表（典型 knowledge_table 内容），VLM 返回空列表，页面进入 unresolved。
        KnowledgeChunk 的 VLM 兜底提取不在本次 Sprint 范围内。
        """
        for attempt in range(max_retries + 1):
            try:
                img_b64 = self.render_page_image(fitz_page)
                prompt = self._build_prompt(page_num, page_type)
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ]
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                    extra_body={"enable_thinking": False},
                )
                raw_content = resp.choices[0].message.content
                return self._validate(raw_content, page_num)
            except Exception as e:
                print(f"[vlm_fallback] Page {page_num} attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # 1s, 2s 指数退避
                    continue
                return []

    def _build_prompt(self, page_num: int, page_type: str) -> str:
        return (
            f"这是工艺技术手册第{page_num}页（类型：{page_type}）的截图。\n"
            "请仔细分析图中的表格，提取所有参数行。只输出 JSON，不要任何解释文字。\n"
            "输出 JSON 数组，每项格式：\n"
            '{"operation_type":"","material_grade":"","parameter_name":"","value":"","unit":"",'
            '"conditions":"{}","table_ref":"","source_page":0}\n'
            "conditions 为 JSON 字符串，存储其他约束条件（如模数、精度等级等）。\n"
            "table_ref 必须非空，无编号时用页码格式如\"P42\"。\n"
            "若无参数表可提取，返回空数组 []。"
        )

    def _validate(self, raw: str, page_num: int) -> list:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            # Accept both top-level array and {"params": [...]} wrapper
            if isinstance(data, dict):
                data = data.get("params", data.get("data", []))
            if not isinstance(data, list):
                return []
            results = []
            for item in data:
                item["source_page"] = page_num
                item["extraction_method"] = "vlm_fallback"
                item["cross_validated"] = 0
                # Ensure table_ref is not empty
                if not item.get("table_ref", "").strip() or item.get("table_ref") in (
                    "未标注",
                    "无",
                    "",
                ):
                    item["table_ref"] = f"P{page_num}"
                # Ensure conditions is a valid JSON string
                conditions = item.get("conditions", {})
                if isinstance(conditions, dict):
                    item["conditions"] = json.dumps(conditions, ensure_ascii=False)
                elif not isinstance(conditions, str):
                    item["conditions"] = "{}"
                try:
                    ProcessParam.model_validate(item)
                    results.append(item)
                except (ValidationError, Exception):
                    continue
            return results
        except (json.JSONDecodeError, Exception):
            return []
