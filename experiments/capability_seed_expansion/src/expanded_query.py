"""Experimental query adapter that adds three B1 candidate families on top of
the existing four-family ``KnowledgeQuery``.

This is intentionally **not** production retrieval. It exists so that the B1
evaluation script can measure whether source-backed candidate seeds reduce
``gap_count_by_capability``. Routing is deterministic and keyword-driven; once a
question is recognized as a candidate-family question it bypasses the base
classifier and returns auditable hits drawn from ``candidate_seed.json``. All
other questions delegate to ``KnowledgeQuery`` unchanged.
"""

from __future__ import annotations

from experiments.agent_query_eval.src.query_api import KnowledgeQuery


B1_CANDIDATE_FAMILIES = (
    "standard_clause_records",
    "inspection_records",
    "equipment_capability_records",
)

INTENT_STANDARD_CLAUSE = "standard_clause_query"
INTENT_INSPECTION = "inspection_query"
INTENT_EQUIPMENT = "equipment_capability_query"


class ExpandedKnowledgeQuery:
    def __init__(self, expanded_seed: dict):
        self.seed = expanded_seed
        # KnowledgeQuery only consumes the four base families it knows about.
        # Extra candidate families in the seed are simply ignored by it.
        self._delegate = KnowledgeQuery(expanded_seed)

    def answer_for_agent(self, question: str, context: dict | None = None) -> dict:
        match = self._match_candidate_family(question)
        if match is not None:
            return self._build_candidate_answer(match)
        return self._delegate.answer_for_agent(question, context)

    def classify_intent(self, question: str):  # pragma: no cover - delegated
        return self._delegate.classify_intent(question)

    def _match_candidate_family(self, question: str) -> dict | None:
        std = _match_standard_clause(question, self.seed.get("standard_clause_records", []))
        if std:
            return {"family": "standard_clause_records", "intent": INTENT_STANDARD_CLAUSE, "hits": std}

        insp = _match_inspection(question, self.seed.get("inspection_records", []))
        if insp:
            return {"family": "inspection_records", "intent": INTENT_INSPECTION, "hits": insp}

        equip = _match_equipment(question, self.seed.get("equipment_capability_records", []))
        if equip:
            return {"family": "equipment_capability_records", "intent": INTENT_EQUIPMENT, "hits": equip}

        return None

    def _build_candidate_answer(self, match: dict) -> dict:
        hits = match["hits"]
        warnings: list[dict] = []
        for hit in hits:
            if hit.get("quality_status") == "accepted_with_flags":
                warnings.append(
                    {
                        "code": "accepted_with_flags",
                        "record_id": hit.get("id"),
                        "flags": hit.get("quality_flags", []),
                    }
                )
            elif hit.get("quality_status") == "needs_human_review":
                warnings.append(
                    {
                        "code": "needs_human_review",
                        "record_id": hit.get("id"),
                        "flags": hit.get("quality_flags", []),
                    }
                )
        return {
            "intent": match["intent"],
            "candidate_type": match["family"],
            "status": "answered" if hits else "not_found",
            "hits": hits,
            "citations": _collect_citations(hits),
            "warnings": warnings,
        }


def _format_candidate_hit(record: dict) -> dict:
    return {
        "id": record["id"],
        "knowledge_type": record["knowledge_type"],
        "family": record["family"],
        "subtype": record.get("subtype"),
        "topic": record.get("topic"),
        "quality_status": record["quality_status"],
        "quality_flags": record.get("quality_flags", []),
        "source_doc": record["source_doc"],
        "source_page": record["source_page"],
        "source_ref": record.get("source_ref"),
        "table_ref": record.get("source_ref"),
        "source_text": record["source_text"],
        "tags": record.get("tags", []),
        "result_json": record.get("result_json"),
        "method_json": record.get("method_json"),
        "guidance_json": record.get("guidance_json"),
    }


def _collect_citations(hits: list[dict]) -> list[dict]:
    citations = []
    for hit in hits:
        citations.append(
            {
                "source_doc": hit.get("source_doc"),
                "source_page": hit.get("source_page"),
                "table_ref": hit.get("table_ref") or hit.get("source_ref", ""),
                "source_text": hit.get("source_text"),
            }
        )
    return citations


_KIND_SIGNALS = {
    "linear": ("线性",),
    "angular": ("角度",),
    "edge_round_chamfer": ("倒圆", "倒角"),
    "linearity_flatness": ("直线度", "平面度"),
    "perpendicularity": ("垂直度",),
    "symmetry": ("对称度",),
    "runout": ("圆跳动",),
}


def _match_standard_clause(question: str, records: list[dict]) -> list[dict]:
    if not records:
        return []
    text = question
    has_1804 = "1804" in text or "GB/T 1804" in text
    has_1184 = "1184" in text or "GB/T 1184" in text
    has_general_tol = "未注公差" in text or "未注一般公差" in text
    if not (has_1804 or has_1184 or has_general_tol):
        return []

    scored: list[tuple[int, dict]] = []
    for record in records:
        rj = record.get("result_json") or {}
        gj = record.get("guidance_json") or {}
        kind = rj.get("kind")
        levels = rj.get("level_codes") or (
            [rj["level_code"]] if rj.get("level_code") else []
        )
        if not levels and gj.get("level_choices"):
            levels = list(gj["level_choices"])

        score = 0
        if has_1804 and "1804" in record["source_doc"]:
            score += 3
        if has_1184 and "1184" in record["source_doc"]:
            score += 3
        if has_general_tol:
            score += 1

        for signal in _KIND_SIGNALS.get(kind or "", ()):
            if signal in text:
                score += 5

        for level in levels:
            for marker in (f"1804-{level}", f"1804—{level}", f"1184-{level}", f"1184—{level}"):
                if marker.lower() in text.lower():
                    score += 8
                    break

        if "标注" in text and "notation" in record.get("subtype", ""):
            score += 6

        if score > 0:
            scored.append((score, record))

    if not scored and has_general_tol and "线性" in text:
        for record in records:
            if record.get("subtype") == "general_tolerance_linear_m":
                scored.append((1, record))
                break

    if not scored and (has_1804 or has_1184) and "标注" in text:
        for record in records:
            if "notation" in record.get("subtype", ""):
                scored.append((1, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]


def _match_inspection(question: str, records: list[dict]) -> list[dict]:
    if not records:
        return []
    text = question
    has_position = "位置度" in text
    has_runout = "圆跳动" in text
    has_coax = "同轴度" in text
    has_symmetry = "对称度" in text
    has_datum = ("基准" in text or "B C" in text or "B、C" in text or "datum" in text.lower())
    has_instrument = any(
        k in text for k in ("检具", "偏摆仪", "量块", "三坐标", "测量方法", "测量机", "CMM", "cmm")
    )

    is_position_with_datum = has_position and has_datum
    is_runout_inspection = has_runout and has_datum and has_instrument or (has_runout and ("如何" in text and "检验" in text))
    is_coax_inspection = has_coax and has_datum and has_instrument
    is_symmetry_specific = has_symmetry and has_instrument

    if not (is_position_with_datum or is_runout_inspection or is_coax_inspection or is_symmetry_specific):
        return []

    scored: list[tuple[int, dict]] = []
    for record in records:
        subtype = record.get("subtype", "")
        score = 0
        if is_position_with_datum and "position" in subtype:
            score += 12
        if is_runout_inspection and "runout" in subtype:
            score += 10
        if is_coax_inspection and "coaxiality" in subtype:
            score += 10
        if is_symmetry_specific and "symmetry" in subtype:
            score += 10
        if has_datum and "datum" in subtype:
            score += 2
        if has_instrument:
            score += 1
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]


def _match_equipment(question: str, records: list[dict]) -> list[dict]:
    if not records:
        return []
    text = question
    equipment_names = ("数控车床", "三轴加工中心", "加工中心", "普通车床", "车床")
    has_equip_name = any(name in text for name in equipment_names)
    has_route_signal = any(k in text for k in ("分配", "如何分工", "分工", "应分配"))
    has_capability_signal = any(
        k in text for k in ("适合", "能加工", "哪些工序", "哪些铣削", "哪些特征", "适用于哪些")
    )

    if not (has_equip_name or has_route_signal):
        return []

    scored: list[tuple[int, dict]] = []
    for record in records:
        subtype = record.get("subtype", "")
        topic = record.get("topic", "")
        rj = record.get("result_json") or {}
        equip_name = rj.get("equipment_name") or ""

        score = 0
        if equip_name and equip_name in text:
            score += 8
        for name in equipment_names:
            if name in text and name in topic:
                score += 5
        if has_route_signal and "route_assignment" in subtype:
            score += 10
        if has_capability_signal and "capability" in subtype:
            score += 3
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]
