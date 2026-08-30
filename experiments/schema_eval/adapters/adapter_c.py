"""Adapter for schema_c (EAV / std_attributes)."""

from __future__ import annotations

from .base import BaseAdapter, LookupResult, loc, has_json, has_self_join


class AdapterC(BaseAdapter):
    name = "schema_c"

    def cutting_params(self, *, material=None, operation=None,
                       workpiece_dim_text=None, ra_target_um=None,
                       hardness_filter=None, limit=10) -> LookupResult:
        # EAV: each filter is an EXISTS subquery against std_attributes.
        # Anchor on kb_records to constrain to §2.7.
        exists_clauses = []
        params = []
        if material:
            exists_clauses.append(
                "EXISTS (SELECT 1 FROM std_attributes a_m WHERE a_m.record_id=r.id "
                "AND a_m.row_index=anchor.row_index AND a_m.attr_key='material' "
                "AND a_m.attr_value_text LIKE ?)")
            params.append(f"%{material}%")
        if operation:
            exists_clauses.append(
                "EXISTS (SELECT 1 FROM std_attributes a_o WHERE a_o.record_id=r.id "
                "AND a_o.row_index=anchor.row_index AND a_o.attr_key='operation' "
                "AND a_o.attr_value_text LIKE ?)")
            params.append(f"%{operation}%")
        if workpiece_dim_text:
            exists_clauses.append(
                "EXISTS (SELECT 1 FROM std_attributes a_d WHERE a_d.record_id=r.id "
                "AND a_d.row_index=anchor.row_index AND a_d.attr_key='workpiece_dim_text' "
                "AND a_d.attr_value_text = ?)")
            params.append(workpiece_dim_text)
        if ra_target_um is not None:
            exists_clauses.append(
                "EXISTS (SELECT 1 FROM std_attributes a_ra WHERE a_ra.record_id=r.id "
                "AND a_ra.row_index=anchor.row_index AND a_ra.attr_key='ra_target_um' "
                "AND a_ra.attr_value_num = ?)")
            params.append(ra_target_um)
        where = " AND ".join(["r.framework_branch LIKE '2.7%'"] + exists_clauses) \
                if exists_clauses else "r.framework_branch LIKE '2.7%'"
        sql = f"""
            SELECT DISTINCT anchor.record_id, anchor.row_index
            FROM std_attributes anchor
            JOIN kb_records r ON r.id = anchor.record_id
            WHERE {where}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        anchor_rows = list(cur.fetchall())

        # For each anchor (record_id, row_index), pivot back to a wide-ish
        # row by querying v_widened or std_attributes again.
        result_rows = []
        for ar in anchor_rows:
            cur2 = self.conn.execute(
                "SELECT * FROM v_widened WHERE record_id=? AND row_index=?",
                [ar["record_id"], ar["row_index"]],
            )
            wide = cur2.fetchone()
            if wide:
                result_rows.append(wide)

        return LookupResult(
            rows=result_rows, sql_used=sql.strip(), sql_loc=loc(sql),
            used_json_extract=False,
            used_self_join=has_self_join(sql),
        )

    def path_precision(self, *, path_keyword, feature=None, limit=10):
        # In schema_c, path is stored as attr_key='path' or 'method'.
        # Filter by both then pivot via v_widened.
        sql = """
            SELECT a.record_id, a.row_index,
                   a.attr_value_text AS path_text
            FROM std_attributes a
            JOIN kb_records r ON r.id = a.record_id
            WHERE r.framework_branch LIKE '2.3.2%'
              AND a.attr_key IN ('path', 'method')
              AND a.attr_value_text LIKE ?
            LIMIT ?
        """
        cur = self.conn.execute(sql, [f"%{path_keyword}%", limit])
        anchors = list(cur.fetchall())
        result_rows = []
        for ar in anchors:
            wide = self.conn.execute(
                "SELECT * FROM v_widened WHERE record_id=? AND row_index=?",
                [ar["record_id"], ar["row_index"]],
            ).fetchone()
            if wide:
                wide["path_text"] = ar["path_text"]
                result_rows.append(wide)
        return LookupResult(rows=result_rows, sql_used=sql.strip(), sql_loc=loc(sql),
                            used_self_join=has_self_join(sql))

    def method_economic_it(self, *, method=None, feature=None, limit=10):
        # Need self-join: filter on method AND require it_text exists.
        params = []
        method_clause = ""
        if method:
            method_clause = "AND a_method.attr_value_text LIKE ?"
            params.append(f"%{method}%")
        sql = f"""
            SELECT a_method.record_id, a_method.row_index,
                   a_method.attr_value_text AS method
            FROM std_attributes a_method
            JOIN kb_records r ON r.id = a_method.record_id
                              AND r.framework_branch LIKE '2.8.1.4%'
            JOIN std_attributes a_it ON a_it.record_id = a_method.record_id
                                     AND a_it.row_index = a_method.row_index
                                     AND a_it.attr_key IN ('IT','it')
            WHERE a_method.attr_key = 'method'
              {method_clause}
            LIMIT ?
        """
        cur = self.conn.execute(sql, [*params, limit])
        anchors = list(cur.fetchall())
        result_rows = []
        for ar in anchors:
            wide = self.conn.execute(
                "SELECT * FROM v_widened WHERE record_id=? AND row_index=?",
                [ar["record_id"], ar["row_index"]],
            ).fetchone()
            if wide:
                wide["method"] = ar["method"]
                result_rows.append(wide)
        return LookupResult(rows=result_rows, sql_used=sql.strip(), sql_loc=loc(sql),
                            used_self_join=has_self_join(sql))

    def method_position_error(self, *, feature, limit=10):
        sql = """
            SELECT a_method.record_id, a_method.row_index,
                   a_method.attr_value_text AS method,
                   a_feat.attr_value_text AS feature,
                   a_err.attr_value_text AS error_text
            FROM std_attributes a_method
            JOIN std_attributes a_feat ON a_feat.record_id = a_method.record_id
                                       AND a_feat.row_index = a_method.row_index
                                       AND a_feat.attr_key = 'feature'
            JOIN std_attributes a_err  ON a_err.record_id  = a_method.record_id
                                       AND a_err.row_index = a_method.row_index
                                       AND a_err.attr_key = 'error_mm'
            WHERE a_method.record_id = 'STD-2.3.2-METHOD-ERRORS-001'
              AND a_method.attr_key = 'method'
              AND a_feat.attr_value_text LIKE ?
            LIMIT ?
        """
        cur = self.conn.execute(sql, [f"%{feature}%", limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql),
                            used_self_join=has_self_join(sql))

    def method_ra(self, *, method, stage=None, limit=10):
        # method在 record topic. 找带 RA-* prefix 且 topic 含 method 的 records
        sql = """
            SELECT v.record_id, v.row_index, v.stage, v.material, v.ra_min, v.ra_max
            FROM v_widened v
            JOIN kb_records r ON r.id = v.record_id
            WHERE r.framework_branch LIKE '2.8.2.1%'
              AND r.topic LIKE ?
            LIMIT ?
        """
        cur = self.conn.execute(sql, [f"%{method}%", limit])
        rows = list(cur.fetchall())
        return LookupResult(rows=rows, sql_used=sql.strip(), sql_loc=loc(sql),
                            used_self_join=False)  # uses view; underlying view does GROUP BY pivot
