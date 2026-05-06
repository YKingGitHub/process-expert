"""Uniform return-shape helpers for ``process_calc`` methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalculationResult:
    method_id: str
    result: Any
    unit: str
    steps: list[str] = field(default_factory=list)
    formula: str = ""
    warnings: list[dict] = field(default_factory=list)
    verified: bool = False
    implementation_status: str = "implemented"

    def to_dict(self) -> dict:
        return {
            "method_id": self.method_id,
            "result": self.result,
            "unit": self.unit,
            "steps": list(self.steps),
            "formula": self.formula,
            "warnings": list(self.warnings),
            "verified": self.verified,
            "implementation_status": self.implementation_status,
        }


def build_result(
    method_id: str,
    result: Any,
    *,
    unit: str,
    steps: list[str],
    formula: str,
    warnings: list[dict] | None = None,
    verified: bool = False,
    implementation_status: str = "implemented",
) -> dict:
    """Convenience wrapper used by every method to package its output."""
    if verified and implementation_status == "implemented":
        implementation_status = "verified"
    return CalculationResult(
        method_id=method_id,
        result=result,
        unit=unit,
        steps=list(steps),
        formula=formula,
        warnings=list(warnings or []),
        verified=verified,
        implementation_status=implementation_status,
    ).to_dict()
