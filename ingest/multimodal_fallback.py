"""VLM multimodal fallback — handles pages that fail Tier 1 + Tier 2 extraction."""

import base64
import json
import time

import fitz  # PyMuPDF
from pydantic import ValidationError

from ingest.schemas import ProcessParam, ToleranceFit


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
                    max_tokens=32768,
                    extra_body={"enable_thinking": False},
                )
                finish_reason = getattr(resp.choices[0], 'finish_reason', 'stop')
                if finish_reason != 'stop':
                    print(f"[vlm_fallback] Page {page_num} output truncated (finish_reason={finish_reason})")
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
            "输出 JSON 对象，格式：{\"params\": [...]}\n"
            "params 数组中每项格式：\n"
            '{"operation_type":"","material_grade":"","parameter_name":"","value":"","unit":"",'
            '"conditions":"{}","table_ref":"","source_page":0}\n'
            "conditions 为 JSON 字符串，存储其他约束条件（如模数、精度等级等）。\n"
            "table_ref 必须非空，无编号时用页码格式如\"P42\"。\n"
            "\n"
            "【宽表处理指导】\n"
            "如果图中表格列数较多（如超过6列），请特别注意：\n"
            "1. 必须提取表格中每一列的数据，不能只提取前几列\n"
            "2. 每个单元格对应一条独立记录——同一行不同列的数值必须生成不同记录\n"
            "3. parameter_name 必须包含该数值对应的列标题以保证唯一性，"
            "格式：\"基础参数名(列标题)\"，如 \"单面余量(≤50)\"、\"单面余量(50~120)\"\n"
            "4. operation_type 填写该行的加工方法（如\"砂型铸造后粗铣或刨\"）\n"
            "5. 用 conditions 字段保存完整约束条件（如尺寸范围、精度等级等）\n"
            "6. 仔细辨认表头的合并单元格和多级表头，确保每个数值都关联到正确的列标题\n"
            "\n"
            "若无参数表可提取，返回 {\"params\": []}。"
        )

    def extract_tolerance_vlm(self, fitz_page, page_num: int,
                               max_retries: int = 2) -> list[dict]:
        """VLM 公差提取兜底：渲染页面 PNG → 公差专用 VLM prompt → 校验。

        返回校验通过的 raw dicts 列表，失败返回空列表。
        """
        for attempt in range(max_retries + 1):
            try:
                img_b64 = self.render_page_image(fitz_page)
                prompt = self._build_tolerance_prompt(page_num)
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
                    max_tokens=32768,
                    extra_body={"enable_thinking": False},
                )
                finish_reason = getattr(resp.choices[0], 'finish_reason', 'stop')
                if finish_reason != 'stop':
                    print(f"[vlm_tolerance] Page {page_num} output truncated (finish_reason={finish_reason})")
                raw_content = resp.choices[0].message.content
                return self._validate_tolerance(raw_content, page_num)
            except Exception as e:
                print(f"[vlm_tolerance] Page {page_num} attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return []

    def _build_tolerance_prompt(self, page_num: int) -> str:
        return (
            f"这是工艺技术手册第{page_num}页（类型：tolerance_fits 公差配合表）的截图。\n"
            "请仔细分析图中的公差配合表格，提取所有公差记录。只输出 JSON，不要任何解释文字。\n"
            "输出 JSON 对象，格式：{\"tolerances\": [...]}\n"
            "tolerances 数组中每项格式：\n"
            '{"nominal_min":0,"nominal_max":0,"fit_code":"","upper_deviation":0,'
            '"lower_deviation":0,"tolerance_grade":"","table_ref":"","source_page":0}\n'
            "\n"
            "【关键规则】\n"
            "1. 行 = 尺寸段（如\"大于30至50\"），解析为 nominal_min=30, nominal_max=50\n"
            "2. 列 = 公差代号（如 H7、f6），即 fit_code，保留原始大小写\n"
            "3. 值 = 偏差值，保留正负号。若单位为 μm，必须÷1000转为 mm\n"
            "4. 多列宽表必须逐列提取，不能只取前几列\n"
            "5. fit_code 只保留字母+数字（如 H7、f6、JS9），不含中文\n"
            "6. table_ref 不得为空，无编号时用页码格式如\"P42\"\n"
            "7. 合并单元格的尺寸段适用于所有子行\n"
            "\n"
            "若无公差表可提取，返回 {\"tolerances\": []}。"
        )

    def _validate_tolerance(self, raw: str, page_num: int) -> list[dict]:
        """JSON 解析 + ToleranceFit schema 校验，返回校验通过的 raw dicts。"""
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                data = data.get("tolerances", data.get("data", []))
            if not isinstance(data, list):
                return []
            results = []
            for item in data:
                item["source_page"] = page_num
                item["extraction_method"] = "vlm_fallback"
                if not item.get("table_ref", "").strip() or item.get("table_ref") in ("未标注", "无", ""):
                    item["table_ref"] = f"P{page_num}"
                if item.get("fit_code"):
                    item["fit_code"] = item["fit_code"].strip()
                # Deviation type conversion
                for key in ("upper_deviation", "lower_deviation", "nominal_min", "nominal_max"):
                    if item.get(key) is not None:
                        try:
                            item[key] = float(item[key])
                        except (ValueError, TypeError):
                            item[key] = None
                try:
                    ToleranceFit.model_validate(item)
                    results.append(item)
                except (ValidationError, Exception):
                    continue
            return results
        except (json.JSONDecodeError, Exception):
            return []

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
