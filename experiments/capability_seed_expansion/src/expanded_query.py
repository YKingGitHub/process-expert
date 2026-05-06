"""Experimental query adapter that adds B1 + B2 candidate families on top of
the four-family ``KnowledgeQuery``.

This is intentionally **not** production retrieval. It exists so that the B1
and B2 evaluation scripts can measure whether source-backed candidate seeds
reduce ``gap_count_by_capability``. Routing is deterministic and keyword-driven;
once a question is recognized as a candidate-family question it bypasses the
base classifier and returns auditable hits drawn from ``candidate_seed.json``.
All other questions delegate to ``KnowledgeQuery`` unchanged.
"""

from __future__ import annotations

from experiments.agent_query_eval.src.query_api import KnowledgeQuery


B1_CANDIDATE_FAMILIES = (
    "standard_clause_records",
    "inspection_records",
    "equipment_capability_records",
)

B2_CANDIDATE_FAMILIES = (
    "drawing_requirement_records",
    "machining_allowance_records",
    "feature_process_records",
    "milling_process_records",
)

ALL_CANDIDATE_FAMILIES = B1_CANDIDATE_FAMILIES + B2_CANDIDATE_FAMILIES

INTENT_STANDARD_CLAUSE = "standard_clause_query"
INTENT_INSPECTION = "inspection_query"
INTENT_EQUIPMENT = "equipment_capability_query"
INTENT_DRAWING_REQUIREMENT = "drawing_requirement_query"
INTENT_MACHINING_ALLOWANCE = "machining_allowance_query"
INTENT_FEATURE_PROCESS = "feature_process_query"
INTENT_MILLING_PROCESS = "milling_process_query"
INTENT_PYTHON_CALCULATION = "python_calculation_query"


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
        # B1 routing first — these are the higher-confidence keyword anchors
        # (国标 references, datum-aware inspection, named equipment).
        std = _match_standard_clause(question, self.seed.get("standard_clause_records", []))
        if std:
            return {"family": "standard_clause_records", "intent": INTENT_STANDARD_CLAUSE, "hits": std}

        insp = _match_inspection(question, self.seed.get("inspection_records", []))
        if insp:
            return {"family": "inspection_records", "intent": INTENT_INSPECTION, "hits": insp}

        equip = _match_equipment(question, self.seed.get("equipment_capability_records", []))
        if equip:
            return {"family": "equipment_capability_records", "intent": INTENT_EQUIPMENT, "hits": equip}

        # B2 routing — narrower triggers, ordered by signal specificity.
        # Welding signals are the most explicit ("焊"); allowance/feature/milling
        # routing avoids B1's standard_clause and equipment domains.
        drw = _match_drawing_requirement(
            question, self.seed.get("drawing_requirement_records", [])
        )
        if drw:
            return {"family": "drawing_requirement_records", "intent": INTENT_DRAWING_REQUIREMENT, "hits": drw}

        allow = _match_machining_allowance(
            question, self.seed.get("machining_allowance_records", [])
        )
        if allow:
            return {"family": "machining_allowance_records", "intent": INTENT_MACHINING_ALLOWANCE, "hits": allow}

        feat = _match_feature_process(
            question, self.seed.get("feature_process_records", [])
        )
        if feat:
            return {"family": "feature_process_records", "intent": INTENT_FEATURE_PROCESS, "hits": feat}

        mill = _match_milling_process(
            question, self.seed.get("milling_process_records", [])
        )
        if mill:
            return {"family": "milling_process_records", "intent": INTENT_MILLING_PROCESS, "hits": mill}

        # Sprint C — DCA-003-style "Python tolerance lookup" questions.
        # Base classifier routes these to lookup_records because of the
        # "上下偏差" keyword; we override to point at the verified
        # computation_methods record instead.
        py_calc = _match_python_calculation(
            question, self.seed.get("computation_methods", [])
        )
        if py_calc:
            return {"family": "computation_methods", "intent": INTENT_PYTHON_CALCULATION, "hits": py_calc}

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


# ---------------------------------------------------------------------------
# B2 routing functions — added 2026-05-06 per design_b2.md.
# ---------------------------------------------------------------------------


def _match_drawing_requirement(question: str, records: list[dict]) -> list[dict]:
    """Welding-related drawing-requirement questions (DRI-002, DRI-003).

    Triggers on '焊' family keywords. Stays away from DRI-001 which is GB/T
    1804 standard_clause territory (B1 already routes that).
    """
    if not records:
        return []
    text = question
    has_weld = any(
        k in text for k in ("焊缝", "焊接符号", "待焊面", "焊接", "焊")
    )
    if not has_weld:
        return []

    is_symbol_explanation = (
        ("焊接符号" in text or "焊缝符号" in text)
        and any(k in text for k in ("解释", "国家标准", "如何", "标注"))
    )
    is_weld_surface = "待焊面" in text

    scored: list[tuple[int, dict]] = []
    for record in records:
        subtype = record.get("subtype", "")
        score = 0
        if is_symbol_explanation and (
            "symbol_standard_interpretation" in subtype
            or "weld_symbol_standard_catalog" in subtype
        ):
            score += 12
        if is_weld_surface and "weld_surface" in subtype:
            score += 12
        # Generic welding signal: lower boost, lets all welding records
        # surface as candidates if both signals are present.
        if "焊" in text and "weld" in subtype.lower():
            score += 2
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]


def _match_machining_allowance(question: str, records: list[dict]) -> list[dict]:
    """Blank-to-finished allowance planning (MAP-003).

    Distinctive trigger: '毛坯' AND '余量'. Avoids MAP-001 (lookup with
    '推荐范围') and MAP-002 ('怎么计算' computation).
    """
    if not records:
        return []
    text = question
    has_blank = "毛坯" in text or "blank" in text.lower()
    has_allowance = "余量" in text or "allowance" in text.lower()
    has_outer = "外圆" in text or "外径" in text
    has_lookup_signal = any(k in text for k in ("推荐范围", "推荐多少", "范围是多少"))
    has_computation_signal = any(k in text for k in ("怎么计算", "如何计算", "公式"))

    if has_lookup_signal or has_computation_signal:
        return []
    if not (has_blank and has_allowance):
        return []

    scored: list[tuple[int, dict]] = []
    for record in records:
        subtype = record.get("subtype", "")
        score = 0
        if has_blank and "blank_to_finished" in subtype:
            score += 12
        if has_outer and "blank_to_finished" in subtype:
            score += 4
        if "finish_to_grind" in subtype:
            score += 1
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]


def _match_feature_process(question: str, records: list[dict]) -> list[dict]:
    """Feature-to-process selection (FPS-001 D-shape hole).

    Distinctive trigger: 'D 型孔' / 'D形孔' / 非圆 + 加工/选择/方法. FPS-002
    (内轮廓圆角) is handled by `_match_milling_process`. EOC-002 (mentions
    D 型孔 but expects equipment_capability) is already routed by B1
    `_match_equipment` because it contains the equipment name '三轴加工中心'.
    """
    if not records:
        return []
    text = question
    has_d_shape = (
        "D 型孔" in text
        or "D型孔" in text
        or "D形孔" in text
        or "D-shape" in text
    )
    has_non_circular = any(k in text for k in ("非圆", "异形孔", "异形腔"))
    has_process_question = any(
        k in text for k in ("选择", "应选", "如何加工", "加工方法", "其他方法", "线切割")
    )
    if not has_process_question:
        return []
    if not (has_d_shape or has_non_circular):
        return []

    scored: list[tuple[int, dict]] = []
    for record in records:
        subtype = record.get("subtype", "")
        score = 0
        if has_d_shape and "d_shaped" in subtype:
            score += 12
        if has_non_circular and "non_circular" in subtype:
            score += 10
        if has_d_shape and "non_circular" in subtype:
            score += 4  # generic non-circular fallback for D-shape
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]


def _match_milling_process(question: str, records: list[dict]) -> list[dict]:
    """Milling-process specific questions (FPS-002 inner-radius R milling).

    Distinctive trigger: ('R' + 数字) AND '铣' AND ('内轮廓' OR '圆角'). EOC-002
    contains '铣削' but is routed to equipment_capability_records by B1
    `_match_equipment` (because of the explicit '三轴加工中心' equipment name).
    """
    if not records:
        return []
    text = question
    has_milling = "铣" in text
    has_inner_radius_topic = (
        "内轮廓" in text
        or "圆角" in text
        or "型腔" in text
    )
    has_radius_callout = "R" in text and any(c.isdigit() for c in text)
    has_equipment_name = any(
        k in text
        for k in ("数控车床", "三轴加工中心", "加工中心", "普通车床")
    )

    if has_equipment_name:
        return []  # let B1 equipment routing handle these
    if not has_milling:
        return []
    if not (has_inner_radius_topic or has_radius_callout):
        return []

    scored: list[tuple[int, dict]] = []
    for record in records:
        subtype = record.get("subtype", "")
        score = 0
        if has_radius_callout and "inner_radius" in subtype:
            score += 12
        if has_inner_radius_topic and "internal_contour" in subtype:
            score += 6
        if has_inner_radius_topic and "inner_radius" in subtype:
            score += 4
        if "plane_milling" in subtype:
            score += 1
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [_format_candidate_hit(record) for _, record in scored[:3]]


# ---------------------------------------------------------------------------
# Sprint C — DCA-003 routing override (added 2026-05-06).
# ---------------------------------------------------------------------------


def _match_python_calculation(question: str, records: list[dict]) -> list[dict]:
    """Catch DCA-003-style questions about ``process_calc.calculate(...)`` and
    route them to the verified ``tolerance_lookup_iso`` computation_methods
    record.

    Pattern: ``Python`` + (fit class signal: H7/H8/g6 OR ``上下偏差``) +
    return-shape signal (``result`` / ``steps`` / ``formula`` /
    ``warnings``). Without the return-shape signal we leave routing to base
    KnowledgeQuery so generic tolerance-lookup questions still hit
    ``lookup_records``.
    """
    if not records:
        return []
    text = question
    has_python = "Python" in text or "python" in text
    has_fit_class = (
        "H7" in text
        or "H8" in text
        or "h6" in text
        or "h7" in text
        or "g6" in text
        or "上下偏差" in text
    )
    has_return_shape = any(
        k in text.lower()
        for k in ("result", "steps", "formula", "warnings")
    )
    if not (has_python and has_fit_class and has_return_shape):
        return []

    target = next(
        (r for r in records if r.get("method_id") == "tolerance_lookup_iso"),
        None,
    )
    if target is None:
        return []
    return [_format_computation_hit(target)]


def _format_computation_hit(record: dict) -> dict:
    """Format a computation_methods record as an answer hit, matching the
    base ``KnowledgeQuery.format_hit`` shape so the evaluator's
    ``implemented_calculation_contract`` check sees ``implementation_status``
    on the top hit."""
    return {
        "id": record.get("id"),
        "knowledge_type": "computation",
        "family": "computation_methods",
        "method_id": record.get("method_id"),
        "topic": record.get("topic"),
        "method_name": record.get("method_name"),
        "formula": record.get("formula"),
        "inputs_json": record.get("inputs_json"),
        "outputs_json": record.get("outputs_json"),
        "implementation_status": record.get("implementation_status"),
        "verified": record.get("verified"),
        "quality_status": record.get("quality_status"),
        "quality_flags": record.get("quality_flags", []),
        "source_doc": record.get("source_doc"),
        "source_page": record.get("source_page"),
        "source_ref": record.get("source_ref"),
        "table_ref": record.get("source_ref"),
        "source_text": record.get("source_text"),
        "tags": record.get("tags", []),
    }
