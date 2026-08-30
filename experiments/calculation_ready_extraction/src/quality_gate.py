"""Deterministic quality gates for source-PDF VLM process-card output."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from experiments.vlm_source_pdf_process_cards.src.schema import (
    validate_process_card_payload,
)


FLOAT_RE = r"\d+(?:\.\d+)?"
SYMMETRIC_RE = re.compile(rf"±\s*(?P<value>{FLOAT_RE})")
PAIR_RE = re.compile(
    rf"(?P<upper>[+-]?{FLOAT_RE}|0)\s*/\s*(?P<lower>[+-]?{FLOAT_RE}|0)"
)


@dataclass(frozen=True)
class QualityFlag:
    code: str
    source_page: int | None = None
    card_index: int | None = None
    step_no: int | None = None
    field: str | None = None
    message: str = ""
    expected: object | None = None
    actual: object | None = None

    def to_dict(self) -> dict:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "source_page": self.source_page,
                "card_index": self.card_index,
                "step_no": self.step_no,
                "field": self.field,
                "message": self.message,
                "expected": self.expected,
                "actual": self.actual,
            }.items()
            if value is not None and value != ""
        }


def evaluate_pages(pages: list[dict], gold_payloads: Iterable[dict] = ()) -> dict:
    flags: list[QualityFlag] = []
    page_summaries = []

    for page in pages:
        schema_errors = validate_process_card_payload(strip_private_keys(page))
        schema_errors.extend(page.get("_validation_errors", []))
        if schema_errors:
            flags.append(
                QualityFlag(
                    code="schema_invalid",
                    source_page=page.get("source_page"),
                    message=f"{len(schema_errors)} schema errors",
                    actual=schema_errors,
                )
            )

        cards = page.get("cards", [])
        page_summaries.append(
            {
                "source_page": page.get("source_page"),
                "card_count": len(cards),
                "step_count": sum(len(card.get("steps", [])) for card in cards),
                "schema_error_count": len(schema_errors),
            }
        )

        for card_index, card in enumerate(cards):
            steps = card.get("steps", [])
            if not steps:
                flags.append(
                    QualityFlag(
                        code="zero_step_card",
                        source_page=page.get("source_page"),
                        card_index=card_index,
                        message="Card has no process steps",
                        actual={
                            "part_name": card.get("part_name"),
                            "table_no": card.get("table_no"),
                        },
                    )
                )
            if card.get("is_continuation") and not card.get("part_name"):
                flags.append(
                    QualityFlag(
                        code="continuation_part_missing",
                        source_page=page.get("source_page"),
                        card_index=card_index,
                        message="Continuation card has empty part_name",
                    )
                )

            for step in steps:
                flags.extend(evaluate_step_dimensions(page.get("source_page"), card_index, step))

    for gold in gold_payloads:
        flags.extend(compare_gold_payload(gold, pages))

    return {
        "page_summaries": page_summaries,
        "flag_count": len(flags),
        "flags": [flag.to_dict() for flag in flags],
        "status": "passed_with_flags" if flags else "passed",
    }


def strip_private_keys(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def evaluate_step_dimensions(source_page: int, card_index: int, step: dict) -> list[QualityFlag]:
    flags = []
    for dimension in step.get("dimensions", []):
        expected = expected_deviations(dimension)
        if expected is None:
            continue
        expected_upper, expected_lower = expected
        actual_upper = dimension.get("upper_deviation")
        actual_lower = dimension.get("lower_deviation")
        if not numbers_equal(actual_upper, expected_upper) or not numbers_equal(
            actual_lower, expected_lower
        ):
            flags.append(
                QualityFlag(
                    code="tolerance_sign_mismatch",
                    source_page=source_page,
                    card_index=card_index,
                    step_no=step.get("step_no"),
                    field="dimensions",
                    message="Numeric deviations do not match tolerance/source text",
                    expected={
                        "upper_deviation": expected_upper,
                        "lower_deviation": expected_lower,
                    },
                    actual={
                        "source_text": dimension.get("source_text"),
                        "tolerance_text": dimension.get("tolerance_text"),
                        "upper_deviation": actual_upper,
                        "lower_deviation": actual_lower,
                    },
                )
            )
    return flags


def expected_deviations(dimension: dict) -> tuple[float, float] | None:
    text = " ".join(
        str(dimension.get(key) or "") for key in ("source_text", "tolerance_text")
    )
    symmetric = SYMMETRIC_RE.search(text)
    if symmetric:
        value = float(symmetric.group("value"))
        return value, -value

    pair = PAIR_RE.search(text)
    if pair:
        return float(pair.group("upper")), float(pair.group("lower"))

    return None


def compare_gold_payload(gold: dict, pages: list[dict]) -> list[QualityFlag]:
    flags = []
    source_page = gold.get("source_page")
    page = next((item for item in pages if item.get("source_page") == source_page), None)
    if not page:
        return [
            QualityFlag(
                code="gold_page_missing",
                source_page=source_page,
                message="Gold page has no matching VLM payload",
            )
        ]

    vlm_dims = collect_dimensions(page)
    for gold_dim in collect_dimensions(gold):
        if gold_dim["nominal"] is None:
            continue
        candidates = [
            item
            for item in vlm_dims
            if item["step_no"] == gold_dim["step_no"]
            and item["surface"] == gold_dim["surface"]
            and numbers_equal(item["nominal"], gold_dim["nominal"])
        ]
        if not candidates:
            flags.append(
                QualityFlag(
                    code="gold_dimension_missing",
                    source_page=source_page,
                    step_no=gold_dim["step_no"],
                    field="dimensions",
                    expected=gold_dim,
                )
            )
            continue

        best = candidates[0]
        if not numbers_equal(best["upper_deviation"], gold_dim["upper_deviation"]) or not numbers_equal(
            best["lower_deviation"], gold_dim["lower_deviation"]
        ):
            flags.append(
                QualityFlag(
                    code="gold_dimension_mismatch",
                    source_page=source_page,
                    step_no=gold_dim["step_no"],
                    field="dimensions",
                    message="VLM dimension differs from manual gold",
                    expected=gold_dim,
                    actual=best,
                )
            )
    return flags


def collect_dimensions(payload: dict) -> list[dict]:
    items = []
    for card in payload.get("cards", []):
        for step in card.get("steps", []):
            for dim in step.get("dimensions", []):
                items.append(
                    {
                        "step_no": step.get("step_no"),
                        "operation_name": step.get("operation_name"),
                        "surface": dim.get("surface"),
                        "nominal": dim.get("nominal"),
                        "upper_deviation": dim.get("upper_deviation"),
                        "lower_deviation": dim.get("lower_deviation"),
                        "source_text": dim.get("source_text"),
                    }
                )
    return items


def numbers_equal(left: object, right: object, tol: float = 1e-9) -> bool:
    if left is None or right is None:
        return left is None and right is None
    try:
        return math.isclose(float(left), float(right), abs_tol=tol)
    except (TypeError, ValueError):
        return False
