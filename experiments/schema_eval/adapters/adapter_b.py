"""Adapter for schema_b (拆专表)."""

from __future__ import annotations

from .base import BaseAdapter, LookupResult, loc, has_json, has_self_join


class AdapterB(BaseAdapter):
    name = "schema_b"

    def cutting_params(self, *, material=None, operation=None,
                       workpiece_dim_text=None, ra_target_um=None,
                       hardness_filter=None, limit=10) -> LookupResult:
        # All filters are typed columns on lookup_cutting_params — no JSON.
        clauses = ["1=1"]
        params = []
        if material:
            clauses.append("material LIKE ?")
            params.append(f"%{material}%")
        if operation:
            clauses.append("operation LIKE ?")
            params.append(f"%{operation}%")
        if workpiece_dim_text:
            clauses.append("workpiece_dim_text = ?")
            params.append(workpiece_dim_text)
        if ra_target_um is not None:
            clauses.append("ra_target_um = ?")
            params.append(ra_target_um)
        sql = f"""
            SELECT record_id, row_index, material, tool_type, operation,
                   workpiece_dim_text, ap_segment_text,
                   f_min, f_max, vc_min_mps, vc_max_mps, n_min_rpm, n_max_rpm,
                   ra_target_um
            FROM lookup_cutting_params
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql),
                            used_json_extract=False, used_self_join=False)

    def path_precision(self, *, path_keyword, feature=None, limit=10):
        clauses = ["path_text LIKE ?"]
        params = [f"%{path_keyword}%"]
        if feature:
            clauses.append("feature_kind = ?")
            params.append(feature)
        sql = f"""
            SELECT record_id, row_index, feature_kind, path_text,
                   it_text, it_min, it_max, ra_min, ra_max
            FROM lookup_path_precision
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql))

    def method_economic_it(self, *, method=None, feature=None, limit=10):
        clauses = []
        params = []
        if method:
            clauses.append("method LIKE ?")
            params.append(f"%{method}%")
        if feature:
            clauses.append("feature LIKE ?")
            params.append(f"%{feature}%")
        if not clauses:
            clauses = ["1=1"]
        sql = f"""
            SELECT record_id, row_index, method, feature, it_text, it_min, it_max
            FROM lookup_method_economic_it
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
            FROM lookup_method_position_error
            WHERE feature LIKE ?
            ORDER BY error_mm_min
            LIMIT ?
        """
        cur = self.conn.execute(sql, [f"%{feature}%", limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql))

    def method_ra(self, *, method, stage=None, limit=10):
        clauses = ["method LIKE ?"]
        params = [f"%{method}%"]
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        sql = f"""
            SELECT record_id, row_index, method, stage, material, ra_min, ra_max
            FROM lookup_method_ra
            WHERE {' AND '.join(clauses)}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql))
