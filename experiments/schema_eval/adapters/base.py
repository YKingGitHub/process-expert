"""Adapter base + LookupResult dataclass.

LookupResult captures *both* the data and the friction signals so the
runner can compute friction without re-executing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LookupResult:
    rows: list[dict] = field(default_factory=list)
    sql_used: str = ""
    sql_loc: int = 0                  # SQL non-blank lines
    used_json_extract: bool = False   # used json_extract / json_each
    used_self_join: bool = False      # query has self-join (EAV pattern)
    error: str | None = None

    @property
    def match_count(self) -> int:
        return len(self.rows)


def loc(sql: str) -> int:
    return sum(1 for line in sql.splitlines() if line.strip())


def has_json(sql: str) -> bool:
    s = sql.lower()
    return "json_extract" in s or "json_each" in s


def has_self_join(sql: str) -> bool:
    s = sql.lower()
    # self-join detection: presence of two FROM/JOIN of std_attributes
    return s.count("std_attributes") >= 2


class BaseAdapter:
    """Subclasses implement schema-specific lookup methods."""

    def __init__(self, conn):
        self.conn = conn
        # Make rows return as dicts
        self.conn.row_factory = lambda cur, r: {
            cur.description[i][0]: r[i] for i in range(len(r))
        }

    # ---- common semantic API ----

    def cutting_params(self, *, material: str | None = None,
                       operation: str | None = None,
                       workpiece_dim_text: str | None = None,
                       ra_target_um: float | None = None,
                       hardness_filter: str | None = None,
                       limit: int = 10) -> LookupResult:
        raise NotImplementedError

    def path_precision(self, *, path_keyword: str,
                       feature: str | None = None,
                       limit: int = 10) -> LookupResult:
        raise NotImplementedError

    def method_economic_it(self, *, method: str | None = None,
                            feature: str | None = None,
                            limit: int = 10) -> LookupResult:
        raise NotImplementedError

    def method_position_error(self, *, feature: str,
                               limit: int = 10) -> LookupResult:
        raise NotImplementedError

    def method_ra(self, *, method: str,
                   stage: str | None = None,
                   limit: int = 10) -> LookupResult:
        raise NotImplementedError
