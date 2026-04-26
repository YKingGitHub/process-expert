"""Build source-PDF-backed query seed records from VLM process-card outputs."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from experiments.calculation_ready_extraction.src.calculation import (
    calculate_cylinder_liner_allowance,
)
from experiments.calculation_ready_extraction.src.loader import (
    load_p108_gold,
    load_vlm_pages,
)
from experiments.calculation_ready_extraction.src.quality_gate import evaluate_pages
from experiments.calculation_ready_extraction.src.route_merge import Route, merge_routes


SOURCE_DOC = "工艺知识库.pdf"
SOURCE_KIND = "source_pdf_vlm_process_card"
PROSE_SOURCE_KIND = "source_pdf_vlm_prose"
REPO_ROOT = Path(__file__).resolve().parents[3]
P107_PROSE_FIXTURE = (
    REPO_ROOT
    / "experiments"
    / "prose_principle_extraction"
    / "fixtures"
    / "source"
    / "p107_principles.json"
)


@dataclass(frozen=True)
class BuildResult:
    seed: dict
    report: dict


def build_source_replaced_seed(base_seed: dict) -> BuildResult:
    pages = load_vlm_pages()
    routes = merge_routes(pages)
    quality = evaluate_pages(pages, gold_payloads=[load_p108_gold()])
    routes_by_part = {route.part_name: route for route in routes}

    seed = copy.deepcopy(base_seed)
    replacements: list[dict] = []
    retained: list[dict] = []

    output_shaft = require_route(routes_by_part, "输出轴")
    cylinder_liner = require_route(routes_by_part, "缸套")
    seal_sleeve = require_route(routes_by_part, "密封件定位套")
    allowance = calculate_cylinder_liner_allowance(cylinder_liner)
    prose_principles = load_prose_principles()

    replace_record(
        seed,
        "principle_records",
        "PR-DATUM-AXIS-001",
        output_shaft_datum_principle(output_shaft),
        replacements,
    )
    replace_record(
        seed,
        "principle_records",
        "PR-THIN-WALL-001",
        thin_wall_principle(cylinder_liner),
        replacements,
    )
    replace_record(
        seed,
        "principle_records",
        "PR-HEAT-TREAT-001",
        heat_treatment_principle(output_shaft, cylinder_liner, seal_sleeve),
        replacements,
    )
    replace_record(
        seed,
        "principle_records",
        "PR-INSPECTION-KEYSLOT-001",
        keyslot_principle(prose_principles),
        replacements,
    )

    replace_record(
        seed,
        "lookup_records",
        "LU-ALLOW-GRIND-001",
        grind_allowance_lookup(cylinder_liner, allowance),
        replacements,
    )
    replace_record(
        seed,
        "lookup_records",
        "LU-EQUIP-CA6140-001",
        ca6140_lookup(output_shaft, cylinder_liner),
        replacements,
    )
    replace_record(
        seed,
        "lookup_records",
        "LU-HEAT-45-TEMPER-001",
        temper_lookup(output_shaft),
        replacements,
    )

    replace_record(
        seed,
        "computation_methods",
        "CM-ALLOW-FINISH-GRIND-001",
        allowance_computation_method(cylinder_liner, allowance),
        replacements,
    )

    replace_record(
        seed,
        "case_records",
        "CASE-SHAFT-OUTPUT-001",
        case_record(output_shaft, "轴类"),
        replacements,
    )
    replace_record(
        seed,
        "case_records",
        "CASE-CYLINDER-LINER-001",
        case_record(cylinder_liner, "薄壁套类", quality_status="needs_human_review"),
        replacements,
    )
    replace_record(
        seed,
        "case_records",
        "CASE-SEAL-SLEEVE-001",
        case_record(seal_sleeve, "套类"),
        replacements,
    )

    report = build_report(seed, replacements, retained, routes, quality)
    return BuildResult(seed=seed, report=report)


def output_shaft_datum_principle(route: Route) -> dict:
    selected = steps_by_no(route, [3, 4, 5, 6, 7, 8])
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(route.source_pages),
        "source_text": join_step_text(selected),
        "principle_text": (
            "轴类零件可先加工中心孔和主要外圆，再用一夹一顶或两顶尖等方式保持后续精车、磨削的统一定位基准。"
        ),
        "quality_status": "accepted",
        "extraction_source": extraction_source(route),
    }


def thin_wall_principle(route: Route) -> dict:
    selected = steps_by_no(route, [8, 9, 10, 11])
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(route.source_pages),
        "source_text": join_step_text(selected),
        "principle_text": (
            "薄壁缸套加工应控制夹紧力和支承方式，粗车、精车、磨削分阶段安排，避免因刚性差导致装夹和切削变形。"
        ),
        "quality_status": "accepted",
        "extraction_source": extraction_source(route),
    }


def heat_treatment_principle(*routes: Route) -> dict:
    selected = []
    for route in routes:
        selected.extend(step for step in route.steps if step.get("operation_name") == "热处理")
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(min(route.source_pages) for route in routes),
        "source_text": join_step_text(selected),
        "principle_text": (
            "热处理应按材料和精度要求插入工艺路线；案例中输出轴下料后调质，缸套粗加工阶段安排人工时效和正火，铸件套类先时效再粗精加工。"
        ),
        "quality_status": "accepted",
        "extraction_source": {
            "kind": SOURCE_KIND,
            "source_pages": sorted({page for route in routes for page in route.source_pages}),
        },
    }


def grind_allowance_lookup(route: Route, allowance: dict) -> dict:
    inner = allowance["result"]["inner_finish_to_grind_allowance"]
    outer = allowance["result"]["outer_finish_to_grind_allowance"]
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(route.source_pages),
        "table_ref": route.table_ref,
        "conditions_json": {"previous_operation": "精车", "next_operation": "磨削", "part_name": route.part_name},
        "result_json": {
            "diameter_allowance_mm": inner["diameter_allowance"],
            "single_side_allowance_mm": inner["single_side_allowance"],
            "inner": inner,
            "outer": outer,
        },
        "unit": "mm",
        "source_text": (
            f"内圆: {inner['finish_source']} -> {inner['grind_source']}；"
            f"外圆: {outer['finish_source']} -> {outer['grind_source']}"
        ),
        "quality_status": "accepted",
        "extraction_source": extraction_source(route),
    }


def ca6140_lookup(*routes: Route) -> dict:
    ca_steps = [
        step
        for route in routes
        for step in route.steps
        if "CA6140" in str(step.get("equipment") or "")
    ]
    operations = sorted({step["operation_name"] for step in ca_steps})
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(min(route.source_pages) for route in routes),
        "table_ref": "表 3-89 / 表 3-90",
        "conditions_json": {"equipment": "CA6140"},
        "result_json": {"typical_operations": operations, "equipment_type": "车床"},
        "unit": "",
        "source_text": join_step_text(ca_steps),
        "quality_status": "accepted",
        "extraction_source": {
            "kind": SOURCE_KIND,
            "source_pages": sorted({page for route in routes for page in route.source_pages}),
        },
    }


def temper_lookup(route: Route) -> dict:
    heat_step = next(step for step in route.steps if step.get("operation_name") == "热处理")
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(route.source_pages),
        "table_ref": route.table_ref,
        "conditions_json": {"material": "45钢", "heat_treatment": "调质"},
        "result_json": {"hardness_min_hrc": 28, "hardness_max_hrc": 32},
        "unit": "HRC",
        "source_text": step_text(heat_step),
        "quality_status": "accepted",
        "extraction_source": extraction_source(route),
    }


def allowance_computation_method(route: Route, allowance: dict) -> dict:
    return {
        "source_doc": SOURCE_DOC,
        "source_page": min(route.source_pages),
        "example_json": allowance["result"],
        "implementation_status": "prototype",
        "verified": True,
        "source_text": grind_allowance_lookup(route, allowance)["source_text"],
        "quality_status": "accepted",
        "extraction_source": extraction_source(route),
    }


def case_record(route: Route, part_category: str, quality_status: str = "accepted") -> dict:
    return {
        "source_doc": SOURCE_DOC,
        "first_page": min(route.source_pages),
        "last_page": max(route.source_pages),
        "part_name": route.part_name,
        "part_category": part_category,
        "case_summary": (
            f"{route.part_name}机械加工工艺过程卡，包含"
            f"{'、'.join(unique(step['operation_name'] for step in route.steps))}等工序。"
        ),
        "route_summary": [step["operation_name"] for step in route.steps],
        "route_json": [
            {
                "step_no": step["step_no"],
                "operation_name": step["operation_name"],
                "operation_content": step.get("operation_content", ""),
                "equipment": step.get("equipment", ""),
                "source_page": step.get("source_page"),
            }
            for step in route.steps
        ],
        "source_text": route_source_text(route),
        "quality_status": quality_status,
        "extraction_source": extraction_source(route),
    }


def load_prose_principles(path: Path = P107_PROSE_FIXTURE) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["payload"]["principle_records"]


def keyslot_principle(prose_principles: list[dict]) -> dict:
    record = next(item for item in prose_principles if item["id"] == "PR-INSPECTION-KEYSLOT-001")
    return {
        "source_doc": SOURCE_DOC,
        "source_page": 107,
        "chapter_path": "第3章 机械加工工艺规程制订",
        "topic": record["topic"],
        "subtype": record["principle_type"],
        "principle_text": record["principle_text"],
        "applicable_scenario": record["applicable_scenario"],
        "source_text": record["source_text"],
        "quality_status": "accepted",
        "tags": record["tags"],
        "extraction_source": {
            "kind": PROSE_SOURCE_KIND,
            "source_pages": [107],
            "fixture": str(P107_PROSE_FIXTURE.relative_to(REPO_ROOT)),
            "evidence_region": record["evidence_region"],
            "confidence": record["confidence"],
        },
    }


def replace_record(
    seed: dict, collection: str, record_id: str, updates: dict, replacements: list[dict]
) -> None:
    record = find_record(seed, collection, record_id)
    record.update(updates)
    record["source_replacement_status"] = "source_pdf_vlm_replaced"
    replacements.append(
        {
            "collection": collection,
            "id": record_id,
            "source_pages": record.get("extraction_source", {}).get("source_pages")
            or [record.get("source_page") or record.get("first_page")],
            "quality_status": record.get("quality_status"),
        }
    )


def mark_retained(
    seed: dict, collection: str, record_id: str, reason: str, retained: list[dict]
) -> None:
    record = find_record(seed, collection, record_id)
    record["source_replacement_status"] = "manual_seed_retained"
    record["replacement_blocker"] = reason
    retained.append({"collection": collection, "id": record_id, "reason": reason})


def find_record(seed: dict, collection: str, record_id: str) -> dict:
    for record in seed[collection]:
        if record["id"] == record_id:
            return record
    raise KeyError(f"{collection}.{record_id}")


def require_route(routes_by_part: dict[str, Route], part_name: str) -> Route:
    if part_name not in routes_by_part:
        raise KeyError(f"Missing route for {part_name}")
    return routes_by_part[part_name]


def steps_by_no(route: Route, step_numbers: list[int]) -> list[dict]:
    wanted = set(step_numbers)
    return [step for step in route.steps if step["step_no"] in wanted]


def extraction_source(route: Route) -> dict:
    return {
        "kind": SOURCE_KIND,
        "table_ref": route.table_ref,
        "source_pages": route.source_pages,
        "route_id": route.route_id,
    }


def route_source_text(route: Route) -> str:
    return f"{route.table_ref} {route.part_name}机械加工工艺过程卡；" + join_step_text(route.steps)


def join_step_text(steps: list[dict]) -> str:
    return "；".join(step_text(step) for step in steps)


def step_text(step: dict) -> str:
    equipment = f"，设备 {step['equipment']}" if step.get("equipment") else ""
    return f"工序{step['step_no']} {step['operation_name']}{equipment}: {step.get('operation_content', '')}"


def unique(values) -> list:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def build_report(
    seed: dict,
    replacements: list[dict],
    retained: list[dict],
    routes: list[Route],
    quality: dict,
) -> dict:
    total_records = sum(len(records) for records in seed.values() if isinstance(records, list))
    return {
        "title": "Agent query source seed replacement report",
        "source": "source_pdf_vlm_process_card+prose",
        "source_kinds": [SOURCE_KIND, PROSE_SOURCE_KIND],
        "record_count": total_records,
        "replaced_count": len(replacements),
        "retained_manual_count": len(retained),
        "replacements": replacements,
        "retained_manual_records": retained,
        "routes": [
            {
                "part_name": route.part_name,
                "table_ref": route.table_ref,
                "source_pages": route.source_pages,
                "step_count": len(route.steps),
                "route_flags": route.flags,
            }
            for route in routes
        ],
        "source_quality": {
            "status": quality["status"],
            "flag_count": quality["flag_count"],
            "flags": quality["flags"],
        },
        "known_limits": [
            "The source replacement currently combines process-card VLM outputs with a targeted p107 prose-principle fixture.",
            "The prose extractor is proven for p107 only; broader prose extraction still needs page-range expansion and quality gates.",
            "The cylinder liner route is retained for query testing but marked with source quality flags from p108 validation.",
        ],
    }
