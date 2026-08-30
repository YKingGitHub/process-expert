"""Conservative parsers for numeric signals in operation text."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


NUMBER = r"\d+(?:\.\d+)?"

DIAMETER_RE = re.compile(
    rf"φ\s*(?P<value>{NUMBER})"
    rf"(?:[A-Za-z]+\d*)?"
    rf"\s*(?P<tolerance>"
    rf"\(\s*[+-]?{NUMBER}\s*/\s*[+-]?{NUMBER}\s*\)"
    rf"|[+-]{NUMBER}\s*/\s*[+-]?{NUMBER}"
    rf"|±\s*{NUMBER}"
    rf"|[+-]{NUMBER}"
    rf")?"
    rf"\s*(?:mm)?"
)

ALLOWANCE_RE = re.compile(
    rf"留(?P<kind>精加工|磨削|加工)?余量\s*"
    rf"(?P<value>{NUMBER})(?:\s*[~～]\s*(?P<max_value>{NUMBER}))?\s*mm"
    rf"|留磨量\s*(?P<grind_value>{NUMBER})\s*mm"
)

LENGTH_RE = re.compile(
    rf"(?P<label>总长(?:尺寸)?|保证(?:工件)?总长(?:尺寸)?|保证图样尺寸)"
    rf"\s*(?:为)?\s*(?P<value>{NUMBER})\s*mm"
)

SYMMETRIC_TOLERANCE_RE = re.compile(rf"±\s*(?P<value>{NUMBER})")
SIGNED_PAIR_RE = re.compile(
    rf"(?P<upper>[+-]?{NUMBER})\s*/\s*(?P<lower>[+-]?{NUMBER})"
)
SIGNED_SINGLE_RE = re.compile(rf"(?P<upper>[+]{NUMBER})")


@dataclass(frozen=True)
class ParsedValue:
    kind: str
    value: float
    unit: str
    source: str
    confidence: str = "explicit"
    surface: str = "unknown"
    upper_deviation: float | None = None
    lower_deviation: float | None = None
    max_value: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_operation_content(text: str) -> dict[str, list[dict]]:
    values = {
        "diameters": [value.to_dict() for value in parse_diameters(text)],
        "allowances": [value.to_dict() for value in parse_allowances(text)],
        "lengths": [value.to_dict() for value in parse_lengths(text)],
    }
    return values


def parse_diameters(text: str) -> list[ParsedValue]:
    parsed = []
    for match in DIAMETER_RE.finditer(text):
        source = match.group(0).strip()
        if not source:
            continue
        upper, lower = parse_tolerance(match.group("tolerance") or "")
        parsed.append(
            ParsedValue(
                kind="diameter",
                value=float(match.group("value")),
                unit="mm",
                source=source,
                surface=infer_surface(text, match.start()),
                upper_deviation=upper,
                lower_deviation=lower,
            )
        )
    return parsed


def parse_allowances(text: str) -> list[ParsedValue]:
    parsed = []
    for match in ALLOWANCE_RE.finditer(text):
        source = match.group(0).strip()
        value = match.group("value") or match.group("grind_value")
        max_value = match.group("max_value")
        parsed.append(
            ParsedValue(
                kind="allowance",
                value=float(value),
                max_value=float(max_value) if max_value else None,
                unit="mm",
                source=source,
                surface=infer_surface(text, match.start()),
            )
        )
    return parsed


def parse_lengths(text: str) -> list[ParsedValue]:
    parsed = []
    for match in LENGTH_RE.finditer(text):
        parsed.append(
            ParsedValue(
                kind="length",
                value=float(match.group("value")),
                unit="mm",
                source=match.group(0).strip(),
            )
        )
    return parsed


def parse_tolerance(text: str) -> tuple[float | None, float | None]:
    value = text.strip()
    if not value:
        return None, None

    symmetric = SYMMETRIC_TOLERANCE_RE.search(value)
    if symmetric:
        tol = float(symmetric.group("value"))
        return tol, -tol

    pair = SIGNED_PAIR_RE.search(value.replace("(", "").replace(")", ""))
    if pair:
        return float(pair.group("upper")), float(pair.group("lower"))

    single = SIGNED_SINGLE_RE.search(value)
    if single:
        return float(single.group("upper")), 0.0

    return None, None


def infer_surface(text: str, index: int) -> str:
    window = text[max(0, index - 16) : index]
    if "内径" in window or "内孔" in window:
        return "inner"
    if "外圆" in window or "轴径" in window:
        return "outer"
    return "unknown"
