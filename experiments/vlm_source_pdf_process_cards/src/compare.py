"""Compare source-PDF gold records with previous POC extraction fixtures."""

from __future__ import annotations


def collect_gold_dimensions(payload: dict) -> list[dict]:
    dimensions = []
    for card in payload.get("cards", []):
        for step in card.get("steps", []):
            for dimension in step.get("dimensions", []):
                dimensions.append(
                    {
                        "step_no": step["step_no"],
                        "operation_name": step["operation_name"],
                        "surface": dimension["surface"],
                        "nominal": float(dimension["nominal"]),
                        "upper_deviation": dimension.get("upper_deviation"),
                        "lower_deviation": dimension.get("lower_deviation"),
                        "source_text": dimension.get("source_text", ""),
                    }
                )
    return dimensions


def find_poc_record(records: list[dict], page_num: int, part_name: str, step_no: int) -> dict:
    for record in records:
        if (
            record.get("page_num") == page_num
            and record.get("part_name") == part_name
            and record.get("step_no") == step_no
        ):
            return record
    raise KeyError(f"POC record not found: page={page_num} part={part_name} step={step_no}")


def find_known_p108_poc_mismatches(gold_payload: dict, poc_records: list[dict]) -> list[dict]:
    """Detect the known p108 ±0.05 -> +0.05 extraction issue."""

    mismatches = []
    for step_no in (8, 9):
        record = find_poc_record(poc_records, page_num=108, part_name="缸套", step_no=step_no)
        content = record.get("operation_content", "")
        if "±0.05" in content:
            continue

        gold_dims = [
            dim
            for dim in collect_gold_dimensions(gold_payload)
            if dim["step_no"] == step_no
            and dim["surface"] in ("inner", "outer")
            and dim["nominal"] in (279.2, 300.8)
        ]
        for dim in gold_dims:
            if dim["lower_deviation"] == -0.05 and "+0.05" in content:
                mismatches.append(
                    {
                        "code": "symmetric_tolerance_lost",
                        "page_num": 108,
                        "step_no": step_no,
                        "surface": dim["surface"],
                        "gold_source_text": dim["source_text"],
                        "gold_lower_deviation": dim["lower_deviation"],
                        "poc_content": content,
                    }
                )
    return mismatches
