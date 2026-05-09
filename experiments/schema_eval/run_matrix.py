"""Schema A/B/C × Cutting params query 矩阵 runner.

Loads 5 standard cutting-params queries (sourced from pipeline-eval traces),
runs each on schema_a / schema_b / schema_c, records:
- match_count (data found?)
- sql_loc (query complexity)
- used_json_extract / used_self_join
- a friction label per the same rules as pipeline-eval

Outputs `experiments/schema_eval/results/matrix.json` and a console summary.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from experiments.schema_eval.adapters.adapter_a import AdapterA
from experiments.schema_eval.adapters.adapter_b import AdapterB
from experiments.schema_eval.adapters.adapter_c import AdapterC

DB_A = REPO_ROOT / "experiments" / "framework_driven_seed" / "sqlite" / "framework_seed.db"
DB_B = REPO_ROOT / "experiments" / "schema_eval" / "framework_seed_b.db"
DB_C = REPO_ROOT / "experiments" / "schema_eval" / "framework_seed_c.db"
OUT_PATH = REPO_ROOT / "experiments" / "schema_eval" / "results" / "matrix.json"


# Standard queries grouped by lookup type
CUTTING_QUERIES = [
    {"id": "C1", "intent": "粗车 不锈钢 φ100-150 → vc/f/n", "method": "cutting_params",
     "kwargs": {"material": "不锈钢", "operation": "粗车", "workpiece_dim_text": "100~150"}},
    {"id": "C2", "intent": "精车 不锈钢 φ40-60 → f", "method": "cutting_params",
     "kwargs": {"material": "不锈钢", "operation": "精车", "workpiece_dim_text": "40~60"}},
    {"id": "C3", "intent": "粗车 不锈钢 φ20-40 → vc/f/n", "method": "cutting_params",
     "kwargs": {"material": "不锈钢", "operation": "粗车", "workpiece_dim_text": "20~40"}},
    {"id": "C4", "intent": "粗车 灰铸铁 → vc", "method": "cutting_params",
     "kwargs": {"material": "灰铸铁"}},
    {"id": "C5", "intent": "精车 铸铁 Ra3.2 → f", "method": "cutting_params",
     "kwargs": {"material": "铸铁", "ra_target_um": 3.2}},
]

PATH_QUERIES = [
    {"id": "P1", "intent": "外圆 粗车→半精车 路线 IT/Ra", "method": "path_precision",
     "kwargs": {"path_keyword": "粗车→半精车"}},
    {"id": "P2", "intent": "外圆 粗车→半精车→精车 路线", "method": "path_precision",
     "kwargs": {"path_keyword": "粗车→半精车→精车"}},
]

EC_QUERIES = [
    {"id": "E1", "intent": "镗 经济精度 IT", "method": "method_economic_it",
     "kwargs": {"method": "镗"}},
    {"id": "E2", "intent": "磨 经济精度 IT", "method": "method_economic_it",
     "kwargs": {"method": "磨"}},
]

POS_QUERIES = [
    {"id": "X1", "intent": "孔轴线到基准面 位置精度", "method": "method_position_error",
     "kwargs": {"feature": "孔轴线到基准面"}},
]

RA_QUERIES = [
    {"id": "R1", "intent": "车端面 可达 Ra", "method": "method_ra",
     "kwargs": {"method": "车端面"}},
]

QUERIES = CUTTING_QUERIES + PATH_QUERIES + EC_QUERIES + POS_QUERIES + RA_QUERIES


def _classify(result, expected_match=True):
    if result.error:
        return "error"
    if result.match_count == 0:
        return "no_data"
    if result.used_json_extract or result.used_self_join:
        return "friction"
    return "pass"


def run():
    conn_a = sqlite3.connect(DB_A)
    conn_b = sqlite3.connect(DB_B)
    conn_c = sqlite3.connect(DB_C)
    adapters = {
        "A": AdapterA(conn_a),
        "B": AdapterB(conn_b),
        "C": AdapterC(conn_c),
    }

    results = []
    for q in QUERIES:
        row = {"id": q["id"], "intent": q["intent"], "method": q["method"],
               "by_schema": {}}
        for schema, adapter in adapters.items():
            try:
                method = getattr(adapter, q["method"])
                lr = method(**q["kwargs"])
                outcome = _classify(lr)
            except Exception as e:
                lr = None
                outcome = "error"
                err_msg = f"{type(e).__name__}: {e}"
            else:
                err_msg = None

            row["by_schema"][schema] = {
                "outcome": outcome,
                "match_count": lr.match_count if lr else 0,
                "sql_loc": lr.sql_loc if lr else 0,
                "used_json_extract": lr.used_json_extract if lr else False,
                "used_self_join": lr.used_self_join if lr else False,
                "error": err_msg,
                "sample_row": lr.rows[0] if lr and lr.rows else None,
            }
        results.append(row)

    # Aggregate
    summary = {"by_schema": {}}
    for schema in adapters:
        outcomes = [r["by_schema"][schema]["outcome"] for r in results]
        summary["by_schema"][schema] = {
            "pass": outcomes.count("pass"),
            "friction": outcomes.count("friction"),
            "no_data": outcomes.count("no_data"),
            "error": outcomes.count("error"),
            "avg_sql_loc": round(
                sum(r["by_schema"][schema]["sql_loc"] for r in results) / len(results), 1),
            "json_dependency_rate": round(
                sum(r["by_schema"][schema]["used_json_extract"] for r in results) / len(results), 2),
            "self_join_rate": round(
                sum(r["by_schema"][schema]["used_self_join"] for r in results) / len(results), 2),
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"results": results, "summary": summary},
                                    ensure_ascii=False, indent=2))

    # Console
    print("=" * 60)
    print("Schema A/B/C × Cutting params query matrix")
    print("=" * 60)
    for r in results:
        print(f"\n{r['id']} [{r['method']}] {r['intent']}")
        for schema in ("A", "B", "C"):
            s = r["by_schema"][schema]
            tag = {"pass": "✅", "friction": "🤔", "no_data": "❌", "error": "💥"}[s["outcome"]]
            print(f"  {schema}  {tag} {s['outcome']:8s} match={s['match_count']:3d} "
                  f"loc={s['sql_loc']:2d} json={int(s['used_json_extract'])} "
                  f"sj={int(s['used_self_join'])}")
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for schema in ("A", "B", "C"):
        s = summary["by_schema"][schema]
        print(f"\n{schema}:")
        for k, v in s.items():
            print(f"  {k:25s} {v}")


if __name__ == "__main__":
    run()
