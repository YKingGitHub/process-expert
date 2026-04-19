import argparse
import json
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "data" / "knowledge.db"


def parse_conditions(cond_list: list) -> dict:
    """['key=val', 'key2=val2'] -> {'key': 'val', 'key2': 'val2'}"""
    result = {}
    for item in (cond_list or []):
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def query_params(db_path, material, operation=None, conditions=None):
    t0 = time.perf_counter()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    sql = """
        SELECT material_grade, operation_type, parameter_name,
               parameter_value, parameter_unit, conditions,
               table_ref, source_page, chapter
        FROM cutting_params
        WHERE (material_grade LIKE ? OR material_grade = ?)
    """
    params = [f"%{material}%", material]

    if operation:
        sql += " AND operation_type = ?"
        params.append(operation)

    sql += " ORDER BY operation_type, parameter_name"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    # Python-side conditions filter
    if conditions:
        filtered = []
        for row in rows:
            try:
                row_conds = json.loads(row.get("conditions") or "{}")
            except (json.JSONDecodeError, TypeError):
                row_conds = {}
            if all(row_conds.get(k) == v for k, v in conditions.items()):
                filtered.append(row)
        rows = filtered

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return rows, elapsed_ms


def query_tolerance(db_path, fit_code=None, nominal_size=None):
    """查询公差配合数据。fit_code 如 'H7'，nominal_size 如 50。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM tolerance_fits WHERE 1=1"
    params = []
    if fit_code:
        sql += " AND fit_code = ?"
        params.append(fit_code)
    if nominal_size is not None:
        sql += " AND ? BETWEEN nominal_min AND nominal_max"
        params.append(nominal_size)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def query_equipment(db_path, model_number=None, equipment_type=None):
    """查询设备规格。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM equipment_specs WHERE 1=1"
    params = []
    if model_number:
        sql += " AND model_number LIKE ?"
        params.append(f"%{model_number}%")
    if equipment_type:
        sql += " AND equipment_type LIKE ?"
        params.append(f"%{equipment_type}%")
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def query_surface_standard(db_path, machining_method=None):
    """查询表面粗糙度标准。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM surface_standards WHERE 1=1"
    params = []
    if machining_method:
        sql += " AND machining_method LIKE ?"
        params.append(f"%{machining_method}%")
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def print_table(rows):
    if not rows:
        print("(无匹配结果)")
        return
    headers = ["material_grade", "operation_type", "parameter_name",
               "parameter_value", "parameter_unit", "table_ref", "source_page"]
    col_widths = {h: max(len(h), max((len(str(r.get(h, "") or "")) for r in rows), default=0))
                  for h in headers}
    header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
    sep_line = "-+-".join("-" * col_widths[h] for h in headers)
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(str(row.get(h, "") or "").ljust(col_widths[h]) for h in headers))


def main():
    parser = argparse.ArgumentParser(description="查询工艺参数知识库")
    parser.add_argument("--material", required=True, help="材料牌号，如 45钢")
    parser.add_argument("--operation", help="工序类型，如 车削、精车")
    parser.add_argument("--condition", action="append", metavar="KEY=VAL",
                        help="conditions JSON 字段过滤，可重复，如 --condition 加工条件=切槽")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="知识库 SQLite 路径")
    args = parser.parse_args()

    conditions = parse_conditions(args.condition)
    rows, elapsed_ms = query_params(
        db_path=args.db,
        material=args.material,
        operation=args.operation,
        conditions=conditions or None,
    )
    print_table(rows)
    print(f"\n共 {len(rows)} 条结果 | 查询耗时: {elapsed_ms:.1f}ms")


if __name__ == "__main__":
    main()
