"""Merge VLM process-card pages into calculation-ready routes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Route:
    route_id: str
    part_name: str
    table_ref: str
    source_pages: list[int]
    steps: list[dict] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)

    @property
    def step_numbers(self) -> list[int]:
        return [step["step_no"] for step in self.steps]


def merge_routes(pages: list[dict]) -> list[Route]:
    routes: list[Route] = []

    for page in sorted(pages, key=lambda item: item.get("source_page") or 0):
        for card_index, card in enumerate(page.get("cards", [])):
            steps = card.get("steps", [])
            if not steps:
                continue

            if card.get("is_continuation"):
                target = find_continuation_target(routes, page.get("source_page"), steps)
                if target:
                    target.steps.extend(copy_steps(steps, page.get("source_page")))
                    target.source_pages = unique(target.source_pages + [page.get("source_page")])
                    target.flags.append(
                        {
                            "code": "continuation_merged",
                            "source_page": page.get("source_page"),
                            "card_index": card_index,
                        }
                    )
                    target.steps.sort(key=lambda step: (step["step_no"], step["source_page"]))
                    continue

            part_name = card.get("part_name") or f"unknown_page_{page.get('source_page')}"
            table_ref = card.get("table_no") or card.get("table_ref") or ""
            route = Route(
                route_id=make_route_id(part_name, table_ref, page.get("source_page")),
                part_name=part_name,
                table_ref=table_ref,
                source_pages=[page.get("source_page")],
                steps=copy_steps(steps, page.get("source_page")),
            )
            routes.append(route)

    for route in routes:
        validate_route(route)

    return routes


def find_continuation_target(
    routes: list[Route], source_page: int, continuation_steps: list[dict]
) -> Route | None:
    if not routes or not continuation_steps:
        return None

    first_step = min(step["step_no"] for step in continuation_steps)
    for route in reversed(routes):
        if source_page - max(route.source_pages) not in (0, 1, 2):
            continue
        if not route.steps:
            continue
        last_step = max(route.step_numbers)
        if first_step in (last_step, last_step + 1):
            return route
    return None


def validate_route(route: Route) -> None:
    numbers = route.step_numbers
    if not numbers:
        route.flags.append({"code": "empty_route"})
        return

    expected = list(range(min(numbers), max(numbers) + 1))
    if numbers != expected:
        route.flags.append(
            {
                "code": "non_continuous_steps",
                "expected": expected,
                "actual": numbers,
            }
        )


def copy_steps(steps: list[dict], source_page: int) -> list[dict]:
    copied = []
    for step in steps:
        item = dict(step)
        item["source_page"] = source_page
        copied.append(item)
    return copied


def make_route_id(part_name: str, table_ref: str, source_page: int) -> str:
    base = "_".join(part for part in (part_name, table_ref, str(source_page)) if part)
    return base.replace(" ", "_")


def unique(values: list[int]) -> list[int]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
