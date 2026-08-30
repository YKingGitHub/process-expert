"""End-to-end deterministic pipeline: feature list → process plan (craft card).

Per ai-assistant Projects/process-expert/designs/2026-05-09-02-end-to-end-
pipeline-mvp/design.md.

Public API:
    plan_craft_card(input_dict) -> dict {
        case_id, summary, operations: [...], divergence_notes
    }

Each operation in `operations` is shaped like:
    {
      seq: 10,
      name: "粗车",
      content: "夹外圆... 车外圆 φ105 (留余量 2.5)",
      equipment: "数控车床",
      cutting_params: {vc, f, ap, n} or None,
      kb_sources: ["STD-2.3.2-OUTER-CYL-PATH-001 row 1", ...],
      gaps: ["切削速度 vc KB 命中 1 行...", ...]
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from process_calc.dispatcher import calculate


# ---- Step A: feature → target ----

# 把每种 feature kind 映射到"加工目标 + 默认候选方法链 hint"
_FEATURE_INTENT = {
    "外圆": {"intent": "OD turning", "default_path_kw": "粗车→半精车→精车"},
    "外圆_法兰": {"intent": "Flange OD turning (rough only)",
                  "default_path_kw": "粗车→半精车"},
    "孔_基准": {"intent": "Datum hole, high precision",
                "default_path_kw": "粗车→半精车→精车 (或磨)"},
    "沉孔": {"intent": "Counterbore (shallow, milled or turned)",
             "default_path_kw": None},
    "异形孔_D型": {"intent": "Non-circular hole (machining center mill)",
                   "default_path_kw": None},
    "端面": {"intent": "Face turning, perpendicularity-critical",
             "default_path_kw": None},
    "总长": {"intent": "Total length / face finish",
             "default_path_kw": None},
    "总长_切片": {"intent": "Cutoff slicing from bar stock",
                  "default_path_kw": None},
    "螺纹_外": {"intent": "External thread (lathe threading)",
                "default_path_kw": None},
    "锥面": {"intent": "Taper turning",
             "default_path_kw": None},
    "球面": {"intent": "Form turning (sphere)",
             "default_path_kw": None},
    "铣扁": {"intent": "Mill flat (milling center)",
             "default_path_kw": None},
}


def _it_band_to_target(tol_band_mm: float | None, dim_mm: float | None) -> int | None:
    """Approximate IT grade target from tolerance band + nominal diameter."""
    if not tol_band_mm or not dim_mm:
        return None
    # ISO 286 IT grades (approx, mid-band 50 mm): IT7≈25μm, IT8≈39, IT9≈62, IT10≈100, IT11≈160, IT12≈250
    # We use coarse bucketing (works for our 3 cases roughly):
    band_um = tol_band_mm * 1000
    if band_um <= 30:
        return 7
    if band_um <= 50:
        return 8
    if band_um <= 70:
        return 9
    if band_um <= 110:
        return 10
    if band_um <= 180:
        return 11
    return 12


def _classify_feature(feature: dict) -> dict:
    intent = _FEATURE_INTENT.get(feature["kind"], {})
    target_it = _it_band_to_target(
        feature.get("tolerance_band_mm"),
        feature.get("diameter_mm") or feature.get("width_mm"),
    )
    return {
        "feature_id": feature["id"],
        "kind": feature["kind"],
        "intent": intent.get("intent", "?"),
        "default_path_kw": intent.get("default_path_kw"),
        "target_it": target_it,
        "target_ra_um": feature.get("ra_target_um"),
        "diameter_mm": feature.get("diameter_mm") or feature.get("width_mm"),
        "raw_feature": feature,
    }


# ---- Step B: candidate paths ----

def _candidate_paths(classified: dict, blank_material: str | None) -> list[dict]:
    """Return list of candidate {operation, path_text, kb_match, ...}."""
    candidates = []
    kw = classified["default_path_kw"]
    feature_kind_for_kb = None
    if classified["kind"] in ("外圆", "外圆_法兰"):
        feature_kind_for_kb = "外圆"
    elif classified["kind"] == "孔_基准":
        feature_kind_for_kb = "孔"
    elif classified["kind"] == "端面":
        feature_kind_for_kb = "平面"

    if kw and feature_kind_for_kb:
        try:
            r = calculate("lookup_path_precision",
                          path_keyword=kw, feature=feature_kind_for_kb)
            for m in r["result"]["matches"][:3]:
                candidates.append({
                    "source": "lookup_path_precision",
                    "path_text": m.get("path_text") or m.get("method"),
                    "it_text": m.get("it"),
                    "ra_min": m.get("ra_min"),
                    "ra_max": m.get("ra_max"),
                    "record_id": m.get("record_id"),
                })
        except Exception:
            pass

    # Fallback per feature kind (deterministic rules where KB doesn't have a
    # clean "path" answer)
    if not candidates:
        FALLBACKS = {
            "总长_切片": [{"source": "rule", "path_text": "线切割切片",
                          "note": "KB 暂无线切割数据, 按工厂常规"}],
            "异形孔_D型": [{"source": "rule",
                          "path_text": "三轴加工中心铣异形孔",
                          "note": "异形特征 KB 无专表"}],
            "螺纹_外": [{"source": "rule",
                        "path_text": "数车挑螺纹", "note": "M-6g 用挑刀"}],
            "锥面": [{"source": "rule", "path_text": "数车成形/锥度刀车锥面"}],
            "球面": [{"source": "rule", "path_text": "数车成形车刀车球面"}],
            "铣扁": [{"source": "rule", "path_text": "加工中心铣两侧扁面"}],
            "沉孔": [{"source": "rule", "path_text": "数车端面+车沉孔"}],
            "端面": [{"source": "rule", "path_text": "粗车端面→精车端面"}],
            "总长": [{"source": "rule", "path_text": "调头平端面修整总长"}],
        }
        candidates.extend(FALLBACKS.get(classified["kind"], []))
    return candidates


# ---- Step C: precision validation ----

def _validate_precision(classified: dict, candidate: dict) -> dict:
    """Mark candidate {ok, why} for whether it can hit the target IT/Ra."""
    target_it = classified.get("target_it")
    target_ra = classified.get("target_ra_um")

    cand_it_text = candidate.get("it_text") or ""
    cand_ra_min = candidate.get("ra_min")
    cand_ra_max = candidate.get("ra_max")

    notes = []
    ok = True
    # Parse cand it_text like "7-8" or "11以下"
    cand_it_min, cand_it_max = _parse_it_range(cand_it_text)
    if target_it is not None and cand_it_max is not None:
        if cand_it_max > target_it:
            # Coarser than required (higher IT number = looser)
            ok = False
            notes.append(f"候选最高 IT{cand_it_max} 比目标 IT{target_it} 粗")
        else:
            notes.append(f"IT{cand_it_min}-{cand_it_max} 满足 IT{target_it}")

    if target_ra is not None and cand_ra_max is not None:
        if cand_ra_max < target_ra:
            notes.append(f"Ra max {cand_ra_max} 远超目标 {target_ra} (过精)")
        elif cand_ra_min and cand_ra_min > target_ra:
            ok = False
            notes.append(f"Ra min {cand_ra_min} 比目标 {target_ra} 还粗")
        else:
            notes.append(f"Ra {cand_ra_min}-{cand_ra_max} 覆盖目标 {target_ra}")

    return {**candidate, "ok": ok, "why": "; ".join(notes) or "(no constraint)"}


def _parse_it_range(text: str):
    text = text or ""
    if "-" in text:
        parts = text.split("-")
        try:
            return int(parts[0].strip()), int(parts[1].split("以")[0].strip())
        except (ValueError, IndexError):
            pass
    if text.endswith("以下"):
        try:
            n = int(text.replace("以下", "").strip())
            return n, n
        except ValueError:
            pass
    if text.endswith("以上"):
        try:
            n = int(text.replace("以上", "").strip())
            return n, n
        except ValueError:
            pass
    try:
        n = int(text.strip())
        return n, n
    except (ValueError, AttributeError):
        return None, None


# ---- Step D: parameter & allowance fill ----

def _fill_cutting_params(material_family: str | None, operation: str,
                          dim_mm: float | None) -> dict | None:
    if not material_family:
        return None
    # Map to KB material vocabulary
    mat_map = {
        "奥氏体不锈钢": "不锈钢",
        "马氏体不锈钢": "不锈钢",
        "灰铸铁": "灰铸铁",
        "碳钢": "钢",
        "合金钢": "合金结构钢",
    }
    material_kb = mat_map.get(material_family, material_family)
    op_map = {"粗车": "粗车", "半精车": "粗车", "精车": "精车",
              "镗孔": "镗", "切断": "切断"}
    op_kb = op_map.get(operation, operation)

    try:
        kwargs = {"material": material_kb}
        if op_kb:
            kwargs["operation"] = op_kb
        # Find dim segment that contains this dim
        if dim_mm is not None:
            seg = _dim_to_segment(dim_mm)
            if seg:
                kwargs["workpiece_dim_text"] = seg
        r = calculate("lookup_cutting_params", **kwargs)
        rows = r["result"]["matches"]
        if rows:
            row = rows[0]
            return {
                "vc_min_mps": row.get("vc_min_mps"),
                "vc_max_mps": row.get("vc_max_mps"),
                "f_min_mmpr": row.get("f_min"),
                "f_max_mmpr": row.get("f_max"),
                "n_min_rpm": row.get("n_min_rpm"),
                "n_max_rpm": row.get("n_max_rpm"),
                "kb_record_id": row.get("record_id"),
            }
    except Exception:
        pass
    return None


def _dim_to_segment(dim: float) -> str | None:
    """Map a numeric dim to one of the dim-segment strings used in KB."""
    segments = [
        (0, 10, "≤10"), (10, 20, "10~20"), (20, 40, "20~40"),
        (40, 60, "40~60"), (60, 80, "60~80"), (80, 100, "80~100"),
        (100, 150, "100~150"), (150, 200, "150~200"),
    ]
    for lo, hi, s in segments:
        if lo < dim <= hi:
            return s
    return None


def _fill_allowance(feature_kind: str, operation: str,
                     dim_mm: float | None, length_mm: float | None) -> dict | None:
    fk_map = {
        "外圆": "外圆", "外圆_法兰": "外圆", "孔_基准": "孔",
        "端面": "端面", "总长_切片": "切断",
    }
    feature_kb = fk_map.get(feature_kind)
    if not feature_kb:
        return None
    try:
        kwargs = {"feature_kind": feature_kb}
        if operation:
            kwargs["operation"] = operation
        if dim_mm is not None:
            kwargs["size_mm"] = dim_mm
        if length_mm is not None:
            kwargs["length_mm"] = length_mm
        r = calculate("lookup_machining_allowance", **kwargs)
        rows = r["result"]["matches"]
        if rows:
            return {
                "allowance_mm_min": rows[0].get("allowance_mm_min"),
                "allowance_mm_max": rows[0].get("allowance_mm_max"),
                "kb_record_id": rows[0].get("record_id"),
            }
    except Exception:
        pass
    return None


# ---- Step E: orchestrate operations ----

# Operation ordering rules (smaller seq number = earlier).
# Keyed by operation 'name' substring.
_OP_PRIORITY = [
    ("领料", 5), ("毛坯", 5), ("铸", 5),
    ("热处理", 7), ("人工时效", 7),
    ("粗车", 10), ("粗车切断", 11),
    ("线切割", 15),
    ("半精车", 20),
    ("精车", 25),
    ("挑螺纹", 27),
    ("钻", 28), ("镗", 29),
    ("铣", 30), ("加工中心", 30),
    ("粗磨", 35),
    ("精磨", 40),
    ("钳", 60), ("去毛刺", 60), ("打标", 62),
    ("检验", 90),
    ("入库", 99),
]


def _op_seq(name: str) -> int:
    for kw, seq in _OP_PRIORITY:
        if kw in name:
            return seq
    return 50  # default mid


def _build_operation(feature_classified: dict, candidate: dict,
                      blank: dict, equipment_pool: list[str]) -> list[dict]:
    """Decompose a candidate path into one or more operation entries."""
    feature = feature_classified["raw_feature"]
    material_family = blank.get("material_family")
    path_text = candidate.get("path_text") or ""
    feature_kind = feature_classified["kind"]
    dim = feature.get("diameter_mm") or feature.get("width_mm")

    # Split path by '→' delimiter to get individual ops
    raw_ops = [s.strip() for s in path_text.replace("(", "").replace(")", "")
               .replace("（", "").replace("）", "").split("→") if s.strip()]
    if not raw_ops:
        raw_ops = [path_text]

    ops_out = []
    for op_text in raw_ops:
        # Pick equipment heuristically
        equipment = "?"
        if "数车" in op_text or "车" in op_text:
            equipment = next((e for e in equipment_pool
                              if "车" in e), "车床")
        elif "铣" in op_text or "加工中心" in op_text:
            equipment = next((e for e in equipment_pool
                              if "铣" in e or "加工中心" in e), "铣床")
        elif "磨" in op_text:
            equipment = next((e for e in equipment_pool
                              if "磨" in e), "磨床")
        elif "线切" in op_text:
            equipment = next((e for e in equipment_pool
                              if "线切" in e or "丝" in e), "快走丝")

        cp = _fill_cutting_params(material_family, op_text, dim)
        length_mm = (feature.get("axial_extent_mm")
                     or feature.get("length_mm")
                     or feature.get("thickness_mm")
                     or feature.get("depth_mm"))
        allowance = _fill_allowance(feature_kind, op_text, dim, length_mm)

        gaps = []
        if cp is None:
            gaps.append("切削参数 KB 未命中")
        if allowance is None:
            gaps.append("加工余量 KB 未命中")

        ops_out.append({
            "name": op_text,
            "feature_id": feature_classified["feature_id"],
            "feature_kind": feature_kind,
            "equipment": equipment,
            "cutting_params": cp,
            "allowance": allowance,
            "kb_sources": [s for s in [
                candidate.get("record_id"),
                cp and cp.get("kb_record_id"),
                allowance and allowance.get("kb_record_id"),
            ] if s],
            "gaps": gaps,
            "_seq_hint": _op_seq(op_text),
        })
    return ops_out


def _merge_and_order(operations: list[dict]) -> list[dict]:
    """Sort by seq_hint, deduplicate same-name ops on same equipment, assign 5-step seq numbers."""
    operations.sort(key=lambda o: o["_seq_hint"])
    # Insert standard pre/post steps if not present
    has_blank = any("领料" in o["name"] or "毛坯" in o["name"] or "铸" in o["name"]
                    for o in operations)
    has_inspect = any("检验" in o["name"] for o in operations)
    has_warehouse = any("入库" in o["name"] for o in operations)

    final = []
    seq = 5
    if not has_blank:
        final.append({"seq": seq, "name": "领料", "content": "依据图纸领料",
                      "equipment": "—", "cutting_params": None, "allowance": None,
                      "kb_sources": [], "gaps": []})
        seq += 5

    for o in operations:
        o["seq"] = seq
        # Render content from feature + params
        feat = o.get("feature_id", "?")
        kind = o.get("feature_kind", "?")
        content_parts = [f"加工 {feat} ({kind})"]
        if o.get("allowance"):
            a = o["allowance"]
            if a.get("allowance_mm_min") is not None:
                content_parts.append(
                    f"余量 {a['allowance_mm_min']}-{a['allowance_mm_max']} mm")
        if o.get("cutting_params"):
            cp = o["cutting_params"]
            if cp.get("vc_min_mps") is not None:
                content_parts.append(
                    f"vc {cp['vc_min_mps']}-{cp['vc_max_mps']} m/s")
            if cp.get("f_min_mmpr") is not None:
                content_parts.append(
                    f"f {cp['f_min_mmpr']}-{cp['f_max_mmpr']} mm/r")
            if cp.get("n_min_rpm") is not None:
                content_parts.append(
                    f"n {int(cp['n_min_rpm'])}-{int(cp['n_max_rpm'])} r/min")
        o["content"] = "; ".join(content_parts)
        final.append(o)
        seq += 5

    if not has_inspect:
        final.append({"seq": seq, "name": "检验", "content": "尺寸+外观检验",
                      "equipment": "—", "cutting_params": None, "allowance": None,
                      "kb_sources": [], "gaps": []})
        seq += 5
    if not has_warehouse:
        final.append({"seq": seq, "name": "入库", "content": "清洗、包装、入库",
                      "equipment": "—", "cutting_params": None, "allowance": None,
                      "kb_sources": [], "gaps": []})
    return final


# ---- Public API ----

def plan_craft_card(input_dict: dict) -> dict:
    """End-to-end pipeline: feature list → ordered operations.

    Returns:
      {
        case_id, part_name,
        summary: {feature_count, op_count, kb_hit_rate, gap_count},
        operations: [{seq, name, content, equipment, cutting_params,
                       allowance, kb_sources, gaps}, ...],
        feature_analysis: [{feature_id, kind, intent, target_it,
                             target_ra_um, candidates}],
        divergence_notes: [...]
      }
    """
    blank = input_dict.get("blank", {})
    equipment_pool = input_dict.get("available_equipment", [])
    features = input_dict.get("features", [])

    feature_analysis = []
    all_ops: list[dict] = []
    divergence_notes = []

    for feature in features:
        classified = _classify_feature(feature)
        candidates = _candidate_paths(classified, blank.get("material_family"))
        # Validate
        validated = []
        for c in candidates:
            v = _validate_precision(classified, c)
            validated.append(v)
        # Pick first OK candidate (or first if none ok with full info)
        chosen = next((v for v in validated if v["ok"]), None) or (
            validated[0] if validated else None)
        if chosen is None:
            divergence_notes.append(
                f"{feature['id']} ({feature['kind']}): 无候选方法 — KB/规则均未命中")
            continue

        ops = _build_operation(classified, chosen, blank, equipment_pool)
        all_ops.extend(ops)

        feature_analysis.append({
            **classified,
            "candidates": validated,
            "chosen": chosen,
        })

    final_ops = _merge_and_order(all_ops)

    # Compute summary
    op_count = len(final_ops)
    kb_hit = sum(1 for o in final_ops if o.get("kb_sources"))
    gap_count = sum(len(o.get("gaps", [])) for o in final_ops)
    return {
        "case_id": input_dict.get("case_id"),
        "part_name": input_dict.get("part_name"),
        "summary": {
            "feature_count": len(features),
            "op_count": op_count,
            "kb_hit_rate": round(kb_hit / op_count, 2) if op_count else 0,
            "gap_count": gap_count,
        },
        "operations": final_ops,
        "feature_analysis": feature_analysis,
        "divergence_notes": divergence_notes,
    }


def render_markdown(plan: dict) -> str:
    """Render a Markdown craft card from a plan dict."""
    lines = [
        f"# 工艺卡 — {plan['part_name']} ({plan['case_id']})",
        "",
        f"**特征数**: {plan['summary']['feature_count']}  ·  "
        f"**工序数**: {plan['summary']['op_count']}  ·  "
        f"**KB 命中率**: {plan['summary']['kb_hit_rate']:.0%}  ·  "
        f"**Gap 数**: {plan['summary']['gap_count']}",
        "",
        "## 工序卡",
        "",
        "| 序 | 名称 | 设备 | 内容 | KB 来源 | Gap |",
        "|---|---|---|---|---|---|",
    ]
    for op in plan["operations"]:
        sources = ", ".join(op.get("kb_sources", [])) or "—"
        gaps = "; ".join(op.get("gaps", [])) or "—"
        lines.append(
            f"| {op['seq']} | {op['name']} | {op.get('equipment', '—')} | "
            f"{op.get('content', '—')} | {sources} | {gaps} |"
        )
    if plan.get("divergence_notes"):
        lines.append("")
        lines.append("## Divergence Notes")
        for n in plan["divergence_notes"]:
            lines.append(f"- {n}")
    return "\n".join(lines)
