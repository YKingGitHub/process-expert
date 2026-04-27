"""Build a small SQLite prototype from calculation-ready routes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .route_merge import Route


DDL = """
DROP TABLE IF EXISTS process_allowances;
DROP TABLE IF EXISTS process_dimensions;
DROP TABLE IF EXISTS process_steps;
DROP TABLE IF EXISTS process_routes;

CREATE TABLE process_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id TEXT UNIQUE NOT NULL,
    part_name TEXT NOT NULL,
    table_ref TEXT,
    first_page INTEGER,
    last_page INTEGER,
    step_count INTEGER NOT NULL,
    quality_status TEXT NOT NULL,
    quality_flags TEXT NOT NULL
);

CREATE TABLE process_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id TEXT NOT NULL,
    step_no INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    operation_content TEXT NOT NULL,
    equipment TEXT,
    source_page INTEGER NOT NULL,
    source_text TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    quality_flags TEXT NOT NULL,
    UNIQUE(route_id, step_no, source_page)
);

CREATE TABLE process_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    surface TEXT,
    nominal REAL,
    unit TEXT,
    upper_deviation REAL,
    lower_deviation REAL,
    tolerance_text TEXT,
    source_text TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    quality_flags TEXT NOT NULL
);

CREATE TABLE process_allowances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    allowance_type TEXT,
    value REAL,
    max_value REAL,
    unit TEXT,
    source_text TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    quality_flags TEXT NOT NULL
);
"""


def build_db(routes: list[Route], db_path: Path, quality_flags: list[dict] | None = None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as conn:
        conn.executescript(DDL)
        for route in routes:
            route_quality_flags = flags_for_route(route, quality_flags or [])
            route_status = (
                "accepted"
                if not has_blocking_route_flags(route) and not has_blocking_quality_flags(route_quality_flags)
                else "needs_human_review"
            )
            all_route_flags = route.flags + route_quality_flags
            conn.execute(
                """
                INSERT INTO process_routes (
                    route_id, part_name, table_ref, first_page, last_page,
                    step_count, quality_status, quality_flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route.route_id,
                    route.part_name,
                    route.table_ref,
                    min(route.source_pages),
                    max(route.source_pages),
                    len(route.steps),
                    route_status,
                    json.dumps(all_route_flags, ensure_ascii=False),
                ),
            )
            for step in route.steps:
                cursor = conn.execute(
                    """
                    INSERT INTO process_steps (
                        route_id, step_no, operation_name, operation_content,
                        equipment, source_page, source_text, quality_status, quality_flags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        route.route_id,
                        step["step_no"],
                        step.get("operation_name", ""),
                        step.get("operation_content", ""),
                        step.get("equipment", ""),
                        step["source_page"],
                        step.get("operation_content", ""),
                        route_status,
                        "[]",
                    ),
                )
                step_id = cursor.lastrowid
                for dimension in step.get("dimensions", []):
                    conn.execute(
                        """
                        INSERT INTO process_dimensions (
                            step_id, surface, nominal, unit, upper_deviation,
                            lower_deviation, tolerance_text, source_text,
                            quality_status, quality_flags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            step_id,
                            dimension.get("surface"),
                            dimension.get("nominal"),
                            dimension.get("unit"),
                            dimension.get("upper_deviation"),
                            dimension.get("lower_deviation"),
                            dimension.get("tolerance_text", ""),
                            dimension.get("source_text", ""),
                            route_status,
                            "[]",
                        ),
                    )
                for allowance in step.get("allowances", []):
                    conn.execute(
                        """
                        INSERT INTO process_allowances (
                            step_id, allowance_type, value, max_value, unit,
                            source_text, quality_status, quality_flags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            step_id,
                            allowance.get("allowance_type"),
                            allowance.get("value"),
                            allowance.get("max_value"),
                            allowance.get("unit"),
                            allowance.get("source_text", ""),
                            route_status,
                            "[]",
                        ),
                    )


def has_blocking_route_flags(route: Route) -> bool:
    return any(flag.get("code") in {"non_continuous_steps", "empty_route"} for flag in route.flags)


def flags_for_route(route: Route, quality_flags: list[dict]) -> list[dict]:
    pages = set(route.source_pages)
    return [flag for flag in quality_flags if flag.get("source_page") in pages and flag_applies_to_route(flag, route)]


def flag_applies_to_route(flag: dict, route: Route) -> bool:
    code = flag.get("code")
    if code in {"continuation_part_missing"}:
        return False
    if code == "zero_step_card":
        return False
    return True


def has_blocking_quality_flags(flags: list[dict]) -> bool:
    blocking = {
        "schema_invalid",
        "tolerance_sign_mismatch",
        "gold_dimension_missing",
        "gold_dimension_mismatch",
    }
    return any(flag.get("code") in blocking for flag in flags)
