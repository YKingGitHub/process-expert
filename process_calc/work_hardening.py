"""Work-hardening ratio calculator (per Ch4 §4.2.2 of 金属切削工艺技术手册).

The ratio N expresses how much harder the machined surface layer is compared
to the bulk material:

    N = (H - H_0) / H_0 * 100   (unit: percent)

H is the post-machining surface microhardness (GPa); H_0 is the original
bulk microhardness. The handbook tabulates typical N ranges per machining
method (Ch4 表 4-41), e.g. 普通车和高速车 N=120-150%, 端铣 N=140-160%, etc.
This module gives the deterministic ratio; the table-driven typical-N
records live in the framework-driven seed under §2.8.3.1.
"""

from __future__ import annotations

from process_calc.errors import InputOutOfRangeError
from process_calc.result import build_result


def calculate_work_hardening_ratio(H_gpa: float, H0_gpa: float) -> dict:
    """Return work-hardening ratio N (%).

    Parameters:
      H_gpa:  post-machining surface microhardness, GPa
      H0_gpa: original bulk microhardness, GPa
    """
    if H0_gpa <= 0:
        raise InputOutOfRangeError(
            f"H0_gpa must be positive (got {H0_gpa})"
        )
    if H_gpa <= 0:
        raise InputOutOfRangeError(
            f"H_gpa must be positive (got {H_gpa})"
        )

    delta = H_gpa - H0_gpa
    n_pct = round(delta / H0_gpa * 100, 4)

    steps = [
        f"输入: H={H_gpa} GPa (已加工表面显微硬度), H₀={H0_gpa} GPa (原始基体显微硬度)",
        f"计算硬度增量 ΔH = H - H₀ = {H_gpa} - {H0_gpa} = {round(delta, 4)} GPa",
        f"加工硬化程度 N = ΔH / H₀ × 100% = {round(delta, 4)} / {H0_gpa} × 100% = {n_pct}%",
    ]
    return build_result(
        method_id="work_hardening_ratio",
        result={
            "H_gpa": H_gpa,
            "H0_gpa": H0_gpa,
            "delta_gpa": round(delta, 4),
            "N_percent": n_pct,
        },
        unit="%",
        steps=steps,
        formula="N = (H - H_0) / H_0 * 100  (Ch4 §4.2.2)",
        verified=True,
        implementation_status="verified",
    )
