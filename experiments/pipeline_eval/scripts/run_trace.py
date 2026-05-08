"""Pipeline trace runner.

Usage:
  python3 run_trace.py <trace_module> [--out PATH]

  trace_module is a dotted path under experiments.pipeline_eval.traces, e.g.
  'falan' or 'locating_pin'. The module must export ALL_QUERIES.

For each query the runner dispatches to the right KB API and records
{actual, outcome}. Output goes to results/<trace>.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
import traceback
from pathlib import Path

# Make process_calc importable from this script
REPO_ROOT = Path(__file__).resolve().parents[2].parent  # experiments/pipeline_eval/scripts → repo root
sys.path.insert(0, str(REPO_ROOT))

from process_calc import calculate  # noqa: E402

DB_PATH = REPO_ROOT / "experiments" / "framework_driven_seed" / "sqlite" / "framework_seed.db"


def dispatch(kb_call):
    """Run the call, return a dict {ok, match_count, rows, raw}."""
    kind = kb_call[0]
    try:
        if kind == "path_precision":
            r = calculate("lookup_path_precision", **kb_call[1])
            return {
                "ok": True, "match_count": r["result"]["match_count"],
                "rows": r["result"]["matches"][:5], "raw": r,
            }
        if kind == "economic_precision":
            r = calculate("lookup_economic_precision", **kb_call[1])
            return {
                "ok": True, "match_count": r["result"]["match_count"],
                "rows": r["result"]["matches"][:5], "raw": r,
            }
        if kind == "position_error":
            r = calculate("lookup_method_position_error", **kb_call[1])
            return {
                "ok": True, "match_count": r["result"]["match_count"],
                "rows": r["result"]["matches"][:5], "raw": r,
            }
        if kind == "calc":
            method_id, kwargs = kb_call[1], kb_call[2]
            r = calculate(method_id, **kwargs)
            return {"ok": True, "match_count": 1, "rows": [r["result"]], "raw": r}
        if kind == "raw_sql":
            sql = kb_call[1]
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = [dict(r) for r in conn.execute(sql).fetchall()]
            return {"ok": True, "match_count": len(rows), "rows": rows[:5], "raw": None}
        if kind == "note":
            return {"ok": True, "match_count": 0, "rows": [], "raw": None,
                    "note": kb_call[1]}
        raise ValueError(f"unknown kb_call kind: {kind}")
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "tb": traceback.format_exc(), "match_count": 0, "rows": []}


def run_trace(trace_path: Path):
    spec = importlib.util.spec_from_file_location("trace_mod", trace_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    queries = mod.ALL_QUERIES

    results = []
    for q in queries:
        actual = dispatch(q["kb_call"])
        outcome = q["assess"](actual)
        results.append({
            "id": q["id"],
            "step": q["step"],
            "category": q["category"],
            "input": q["input"],
            "text": q["text"],
            "expected": q["expected"],
            "kb_call": [q["kb_call"][0]] + (
                [str(q["kb_call"][1])[:120]] if len(q["kb_call"]) > 1 else []
            ),
            "actual_match_count": actual.get("match_count"),
            "actual_sample": actual.get("rows", [])[:3],
            "actual_error": actual.get("error"),
            "outcome": outcome,
        })
    return results


def summarize(results):
    counts = {"pass": 0, "partial": 0, "no_data": 0, "friction": 0}
    by_step = {}
    by_category = {}
    for r in results:
        outcome = r["outcome"]
        # Skip Q27 sequence-check from indicator math
        if r["id"] == "Q27":
            continue
        counts[outcome] = counts.get(outcome, 0) + 1
        by_step.setdefault(r["step"], {"pass": 0, "partial": 0, "no_data": 0, "friction": 0})
        by_step[r["step"]][outcome] = by_step[r["step"]].get(outcome, 0) + 1
        by_category.setdefault(r["category"], {"pass": 0, "partial": 0, "no_data": 0, "friction": 0})
        by_category[r["category"]][outcome] = by_category[r["category"]].get(outcome, 0) + 1

    total = sum(counts.values())
    have_data = counts["pass"] + counts["partial"] + counts["friction"]
    coverage = have_data / total if total else 0.0
    accuracy = counts["pass"] / have_data if have_data else 0.0
    friction = counts["friction"] / have_data if have_data else 0.0
    return {
        "totals": counts,
        "total_queries": total,
        "coverage": coverage,
        "accuracy": accuracy,
        "friction": friction,
        "by_step": by_step,
        "by_category": by_category,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_module", help="trace name without extension, e.g. 'falan'")
    ap.add_argument("--out", help="output JSON path (default: results/<name>.json)")
    args = ap.parse_args()

    trace_path = Path(__file__).resolve().parents[1] / "traces" / f"{args.trace_module}.py"
    out_path = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "results" / f"{args.trace_module}.json"
    )

    results = run_trace(trace_path)
    summary = summarize(results)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "summary": summary}, f,
                  ensure_ascii=False, indent=2)

    # console summary
    print(f"=== {args.trace_module}: {summary['total_queries']} queries ===")
    print(f"  totals     {summary['totals']}")
    print(f"  coverage   {summary['coverage']:.1%}  (有数据)")
    print(f"  accuracy   {summary['accuracy']:.1%}  (在有数据中答对)")
    print(f"  friction   {summary['friction']:.1%}  (在有数据中需 ad-hoc SQL)")
    print(f"  by step    {summary['by_step']}")


if __name__ == "__main__":
    main()
