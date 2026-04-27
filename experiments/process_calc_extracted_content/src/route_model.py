"""Route reconstruction for extracted process-card rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


OPERATION_CATEGORIES = {
    "下料": "blank_preparation",
    "铸": "blank_preparation",
    "铸造": "blank_preparation",
    "锻": "blank_preparation",
    "锻造": "blank_preparation",
    "清砂": "treatment_or_auxiliary",
    "清理": "treatment_or_auxiliary",
    "热处理": "treatment_or_auxiliary",
    "涂漆": "treatment_or_auxiliary",
    "涂装": "treatment_or_auxiliary",
    "划线": "treatment_or_auxiliary",
    "车": "rough_or_general_machining",
    "粗车": "rough_or_general_machining",
    "铣": "rough_or_general_machining",
    "粗铣": "rough_or_general_machining",
    "钻": "rough_or_general_machining",
    "镗": "rough_or_general_machining",
    "粗镗": "rough_or_general_machining",
    "刨": "rough_or_general_machining",
    "滚齿": "rough_or_general_machining",
    "精车": "finish_machining",
    "磨": "finish_machining",
    "粗磨": "finish_machining",
    "精镗": "finish_machining",
    "钳": "finish_machining",
    "检": "inspection",
    "检验": "inspection",
    "探伤": "inspection",
    "入库": "storage",
    "技术要求": "technical_requirement",
}


@dataclass(frozen=True)
class ProcessStep:
    id: int
    page_num: int
    toc_path: str
    part_name: str
    table_ref: str
    step_no: int
    operation_name: str
    operation_content: str
    equipment: str
    category: str

    @classmethod
    def from_record(cls, record: dict) -> "ProcessStep":
        operation_name = clean_text(record.get("operation_name"))
        return cls(
            id=int(record["id"]),
            page_num=int(record["page_num"]),
            toc_path=clean_text(record.get("toc_path")),
            part_name=clean_text(record.get("part_name")),
            table_ref=clean_text(record.get("table_ref")),
            step_no=int(record["step_no"]),
            operation_name=operation_name,
            operation_content=clean_text(record.get("operation_content")),
            equipment=clean_text(record.get("equipment")),
            category=normalize_operation(operation_name),
        )


@dataclass
class ProcessRoute:
    canonical_part_name: str
    source_part_names: list[str]
    table_refs: list[str]
    steps: list[ProcessStep] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    @property
    def first_page(self) -> int:
        return min(step.page_num for step in self.steps)

    @property
    def last_page(self) -> int:
        return max(step.page_num for step in self.steps)

    @property
    def step_numbers(self) -> list[int]:
        return [step.step_no for step in self.steps]

    @property
    def categories(self) -> set[str]:
        return {step.category for step in self.steps}

    def append_group(self, group: "ProcessRoute", reason: str) -> None:
        self.steps.extend(group.steps)
        self.steps.sort(key=lambda step: (step.step_no, step.page_num, step.id))
        self.source_part_names = unique_preserve_order(
            self.source_part_names + group.source_part_names
        )
        self.table_refs = unique_preserve_order(self.table_refs + group.table_refs)
        self.warnings.append(
            {
                "code": "continuation_merged",
                "reason": reason,
                "merged_part_names": group.source_part_names,
                "merged_table_refs": group.table_refs,
            }
        )
        self.warnings.extend(group.warnings)

    def validate_sequence(self) -> None:
        if not self.steps:
            self.warnings.append({"code": "empty_route"})
            return

        numbers = self.step_numbers
        expected = list(range(min(numbers), max(numbers) + 1))
        if numbers != expected:
            missing = [number for number in expected if number not in numbers]
            duplicates = sorted(
                {number for number in numbers if numbers.count(number) > 1}
            )
            self.warnings.append(
                {
                    "code": "non_continuous_step_sequence",
                    "expected": expected,
                    "actual": numbers,
                    "missing": missing,
                    "duplicates": duplicates,
                }
            )

        for step in self.steps:
            if step.category == "unknown":
                self.warnings.append(
                    {
                        "code": "unknown_operation_category",
                        "step_no": step.step_no,
                        "operation_name": step.operation_name,
                    }
                )


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_operation(operation_name: str) -> str:
    if operation_name in OPERATION_CATEGORIES:
        return OPERATION_CATEGORIES[operation_name]
    if "检" in operation_name:
        return "inspection"
    if "入库" in operation_name:
        return "storage"
    if any(token in operation_name for token in ("精", "磨", "钳")):
        return "finish_machining"
    if any(token in operation_name for token in ("车", "铣", "钻", "镗", "刨", "齿")):
        return "rough_or_general_machining"
    if any(token in operation_name for token in ("铸", "锻", "下料")):
        return "blank_preparation"
    if any(token in operation_name for token in ("热", "清", "涂", "划线")):
        return "treatment_or_auxiliary"
    return "unknown"


def reconstruct_routes(records: Iterable[dict]) -> list[ProcessRoute]:
    groups = build_initial_groups(records)
    routes: list[ProcessRoute] = []

    for group in sorted(groups, key=lambda route: (route.first_page, min(route.step_numbers))):
        previous = routes[-1] if routes else None
        if previous and should_merge_continuation(previous, group):
            previous.append_group(group, reason=continuation_reason(previous, group))
            continue
        routes.append(group)

    for route in routes:
        route.validate_sequence()

    return routes


def build_initial_groups(records: Iterable[dict]) -> list[ProcessRoute]:
    grouped: dict[tuple[str, str], list[ProcessStep]] = {}
    for record in records:
        if record.get("step_no") is None:
            continue
        step = ProcessStep.from_record(record)
        grouped.setdefault((step.part_name, step.table_ref), []).append(step)

    routes = []
    for (part_name, table_ref), steps in grouped.items():
        steps.sort(key=lambda step: (step.step_no, step.page_num, step.id))
        routes.append(
            ProcessRoute(
                canonical_part_name=canonical_part_name(part_name),
                source_part_names=[part_name],
                table_refs=[table_ref],
                steps=steps,
            )
        )
    return routes


def should_merge_continuation(previous: ProcessRoute, current: ProcessRoute) -> bool:
    if not is_continuation_candidate(current):
        return False

    if current.first_page - previous.last_page not in (0, 1, 2):
        return False

    previous_max = max(previous.step_numbers)
    current_min = min(current.step_numbers)
    step_continues = current_min in (previous_max, previous_max + 1)
    if not step_continues:
        return False

    if same_canonical_part(previous, current):
        return True

    if table_number(previous.table_refs[-1]) and table_number(previous.table_refs[-1]) == table_number(current.table_refs[0]):
        return True

    return False


def is_continuation_candidate(route: ProcessRoute) -> bool:
    text = " ".join(route.source_part_names + route.table_refs)
    return "续" in text


def same_canonical_part(previous: ProcessRoute, current: ProcessRoute) -> bool:
    return previous.canonical_part_name == current.canonical_part_name


def canonical_part_name(part_name: str) -> str:
    value = part_name.replace("（续）", "").replace("(续)", "").strip()
    if value == "轴类零件":
        return "输出轴"
    return value


def table_number(table_ref: str) -> str:
    digits = []
    for char in table_ref:
        if char.isdigit() or char in "-.－":
            digits.append(char.replace("－", "-"))
    return "".join(digits)


def continuation_reason(previous: ProcessRoute, current: ProcessRoute) -> str:
    if same_canonical_part(previous, current):
        return "same canonical part name and continuation table"
    return "continuous step numbers and matching table number"


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
