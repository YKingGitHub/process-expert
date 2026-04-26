"""Minimal AI-facing query API for the calculation-ready prototype DB."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_process_route(db_path: Path, part_name: str) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        route = conn.execute(
            """
            SELECT route_id, part_name, table_ref, first_page, last_page,
                   step_count, quality_status, quality_flags
            FROM process_routes
            WHERE part_name = ?
            """,
            (part_name,),
        ).fetchone()
        if route is None:
            raise KeyError(part_name)
        steps = conn.execute(
            """
            SELECT step_no, operation_name, operation_content, equipment,
                   source_page, quality_status
            FROM process_steps
            WHERE route_id = ?
            ORDER BY step_no, source_page
            """,
            (route["route_id"],),
        ).fetchall()
    return {
        "route": dict(route),
        "steps": [dict(step) for step in steps],
    }


def get_step_dimensions(db_path: Path, part_name: str, step_no: int) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT d.surface, d.nominal, d.unit, d.upper_deviation,
                   d.lower_deviation, d.tolerance_text, d.source_text,
                   d.quality_status
            FROM process_routes r
            JOIN process_steps s ON s.route_id = r.route_id
            JOIN process_dimensions d ON d.step_id = s.id
            WHERE r.part_name = ?
              AND s.step_no = ?
            ORDER BY d.id
            """,
            (part_name, step_no),
        ).fetchall()
    return [dict(row) for row in rows]
