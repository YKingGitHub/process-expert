"""Adapter for schema_a (baseline std_value_rows + extra_json catch-all)."""

from __future__ import annotations

from .base import BaseAdapter, LookupResult, loc, has_json, has_self_join


class AdapterA(BaseAdapter):
    name = "schema_a"

    def cutting_params(self, *, material=None, operation=None,
                       workpiece_dim_text=None, ra_target_um=None,
                       hardness_filter=None, limit=10) -> LookupResult:
        # All cutting params data lives in extra_json (no typed columns
        # for tool_type/operation/ap_segment/f/vc/n in schema_a).
        # Must use json_extract for operation filter.
        clauses = ["r.framework_branch LIKE '2.7%'"]
        params = []
        if material:
            clauses.append("v.material LIKE ?")
            params.append(f"%{material}%")
        if operation:
            clauses.append("json_extract(v.extra_json, '$.operation') LIKE ?")
            params.append(f"%{operation}%")
        if workpiece_dim_text:
            clauses.append("v.workpiece_dim_text = ?")
            params.append(workpiece_dim_text)
        if ra_target_um is not None:
            clauses.append("CAST(json_extract(v.extra_json, '$.ra_target_um') AS REAL) = ?")
            params.append(ra_target_um)
        sql = f"""
            SELECT v.record_id, v.row_index, v.material,
                   v.workpiece_dim_text, v.extra_json
            FROM std_value_rows v
            JOIN kb_records r ON r.id = v.record_id
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(
            rows=rows, sql_used=sql.strip(), sql_loc=loc(sql),
            used_json_extract=has_json(sql), used_self_join=False,
        )

    def path_precision(self, *, path_keyword, feature=None, limit=10):
        clauses = ["r.framework_branch LIKE '2.3.2%'", "v.method LIKE ?"]
        params = [f"%{path_keyword}%"]
        if feature:
            clauses.append("r.topic LIKE ?")
            params.append(f"%{feature}%")
        sql = f"""
            SELECT v.record_id, v.row_index, v.method, v.it, v.it_min, v.it_max,
                   v.ra_min, v.ra_max
            FROM std_value_rows v
            JOIN kb_records r ON r.id = v.record_id
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql),
                            used_json_extract=False, used_self_join=False)

    def method_economic_it(self, *, method=None, feature=None, limit=10):
        clauses = ["r.framework_branch LIKE '2.8.1.4%'", "v.it IS NOT NULL"]
        params = []
        if method:
            clauses.append("v.method LIKE ?")
            params.append(f"%{method}%")
        if feature:
            clauses.append("(v.feature LIKE ? OR r.topic LIKE ?)")
            params.append(f"%{feature}%")
            params.append(f"%{feature}%")
        sql = f"""
            SELECT v.record_id, v.row_index, v.method, v.feature, v.it, v.it_min, v.it_max
            FROM std_value_rows v
            JOIN kb_records r ON r.id = v.record_id
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql))

    def method_position_error(self, *, feature, limit=10):
        sql = """
            SELECT record_id, row_index, method, feature, error_text,
                   error_mm_min, error_mm_max
            FROM std_value_rows
            WHERE record_id = 'STD-2.3.2-METHOD-ERRORS-001'
              AND feature LIKE ?
            ORDER BY error_mm_min
            LIMIT ?
        """
        cur = self.conn.execute(sql, [f"%{feature}%", limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql))

    def method_ra(self, *, method, stage=None, limit=10):
        # method is in record topic, not in row — must search by topic
        clauses = ["r.framework_branch LIKE '2.8.2.1%'", "r.topic LIKE ?"]
        params = [f"%{method}%"]
        if stage:
            clauses.append("v.stage = ?")
            params.append(stage)
        sql = f"""
            SELECT v.record_id, v.row_index, v.stage, v.material, v.ra_min, v.ra_max
            FROM std_value_rows v
            JOIN kb_records r ON r.id = v.record_id
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql))
