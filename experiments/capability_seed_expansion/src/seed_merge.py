"""Merge base agent_query_eval seed with B1 candidate seed into expanded seed."""

from __future__ import annotations

from copy import deepcopy


def build_expanded_seed(
    base: dict[str, list[dict]],
    candidate: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Return a new dict containing every base family unchanged plus B1 candidate
    families. Inputs are not mutated.

    Base families and B1 candidate families are disjoint by design — base owns
    principle/lookup/computation/case/candidate_type, B1 introduces
    standard_clause/inspection/equipment_capability. If they ever collide on a
    family name, candidate records are appended after base records.
    """
    expanded: dict[str, list[dict]] = {
        family: [deepcopy(record) for record in records]
        for family, records in base.items()
    }
    for family, records in candidate.items():
        bucket = expanded.setdefault(family, [])
        bucket.extend(deepcopy(record) for record in records)
    return expanded
