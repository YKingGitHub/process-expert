"""Framework-driven seed record schemas.

Per `Projects/process-expert/designs/2026-05-07-01-machining-design-framework/
design.md` v1.1 — 4 families, fixed prefixes, branch IDs are framework
section numbers.
"""

from __future__ import annotations

import re

FAMILIES = ("经验", "标准", "计算", "案例")
PREFIX_BY_FAMILY = {
    "经验": "EXP",
    "标准": "STD",
    "计算": "CALC",
    "案例": "CASE",
}
ALLOWED_QUALITY_STATUSES = {
    "accepted",
    "accepted_with_flags",
    "needs_human_review",
}
SOURCE_TEXT_MAX_LEN = 240

BASE_REQUIRED_FIELDS = (
    "id",
    "family",
    "prefix",
    "framework_branch",
    "subtype",
    "topic",
    "source_doc",
    "source_page",
    "source_ref",
    "source_text",
    "quality_status",
    "quality_flags",
    "tags",
    "payload",
)

EXPERIENCE_PAYLOAD_FIELDS = ("factor", "impact", "improvement_actions")

# Soft tags for individual improvement_actions. Boundaries are fuzzy, multi-tag
# allowed, empty list = "uncategorized" (matches Sean's caveat that even tags
# won't have crisp boundaries).
ALLOWED_ACTION_TAGS = {
    "principle",    # 规范性陈述 (应当/必须/应保证 语调或逻辑)
    "practice",     # 具体操作做法 (含工具/参数/步骤)
    "observation",  # 实测现象描述
}
STANDARD_PAYLOAD_FIELDS = ("subject",)  # value or value_table required
CALC_PAYLOAD_FIELDS = ("method_id", "formula", "inputs", "outputs")
CASE_PAYLOAD_FIELDS = ("part_name", "route_summary")

ID_PATTERN = re.compile(r"^(EXP|STD|CALC|CASE)-[\d.]+-[A-Z][A-Z0-9-]*-\d{3}$")
BRANCH_PATTERN = re.compile(r"^\d+(\.\d+){0,3}$")


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []
    rid = record.get("id", "?")

    for field in BASE_REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"{rid}: missing field {field!r}")

    if errors:
        return errors

    family = record["family"]
    if family not in FAMILIES:
        errors.append(f"{rid}: family={family!r} not in {FAMILIES}")
    else:
        expected_prefix = PREFIX_BY_FAMILY[family]
        if record["prefix"] != expected_prefix:
            errors.append(
                f"{rid}: prefix={record['prefix']!r} does not match family "
                f"{family!r} (expected {expected_prefix})"
            )
        if not record["id"].startswith(expected_prefix + "-"):
            errors.append(
                f"{rid}: id does not start with prefix {expected_prefix}-"
            )

    if not ID_PATTERN.match(record["id"]):
        errors.append(f"{rid}: id format does not match pattern")

    if not BRANCH_PATTERN.match(record["framework_branch"]):
        errors.append(
            f"{rid}: framework_branch={record['framework_branch']!r} "
            "does not match N(.N)* pattern"
        )

    if record["quality_status"] not in ALLOWED_QUALITY_STATUSES:
        errors.append(
            f"{rid}: quality_status={record['quality_status']!r} not in "
            f"{sorted(ALLOWED_QUALITY_STATUSES)}"
        )

    if record["quality_status"] == "accepted_with_flags" and not record["quality_flags"]:
        errors.append(f"{rid}: accepted_with_flags requires non-empty quality_flags")

    if record["quality_status"] == "needs_human_review" and not record["quality_flags"]:
        errors.append(f"{rid}: needs_human_review requires non-empty quality_flags")

    if not isinstance(record["source_text"], str):
        errors.append(f"{rid}: source_text must be string")
    elif len(record["source_text"]) > SOURCE_TEXT_MAX_LEN:
        errors.append(
            f"{rid}: source_text length {len(record['source_text'])} exceeds "
            f"{SOURCE_TEXT_MAX_LEN}"
        )

    payload = record.get("payload")
    if not isinstance(payload, dict):
        errors.append(f"{rid}: payload must be a dict")
        return errors

    if family == "经验":
        for field in EXPERIENCE_PAYLOAD_FIELDS:
            if field not in payload:
                errors.append(f"{rid}: 经验 payload missing {field!r}")
        actions = payload.get("improvement_actions")
        if actions is not None:
            errors.extend(_validate_actions(rid, actions))

    elif family == "标准":
        if "subject" not in payload:
            errors.append(f"{rid}: 标准 payload missing 'subject'")
        if "value" not in payload and "value_table" not in payload:
            errors.append(f"{rid}: 标准 payload requires 'value' or 'value_table'")

    elif family == "计算":
        for field in CALC_PAYLOAD_FIELDS:
            if field not in payload:
                errors.append(f"{rid}: 计算 payload missing {field!r}")

    elif family == "案例":
        for field in CASE_PAYLOAD_FIELDS:
            if field not in payload:
                errors.append(f"{rid}: 案例 payload missing {field!r}")

    return errors


def _validate_actions(rid: str, actions) -> list[str]:
    """Each improvement_action is ``{text: str, tags: list[str]}``. ``tags``
    is required but may be empty when the action's principle/practice/observation
    classification is ambiguous (Sean's caveat: even tags don't have crisp
    boundaries — empty tags is honest about that)."""
    errors: list[str] = []
    if not isinstance(actions, list):
        return [f"{rid}: improvement_actions must be a list"]
    for index, action in enumerate(actions):
        prefix = f"{rid}.improvement_actions[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{prefix}: must be a dict {{text, tags}}")
            continue
        text = action.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{prefix}: 'text' must be non-empty string")
        tags = action.get("tags")
        if not isinstance(tags, list):
            errors.append(f"{prefix}: 'tags' must be a list (may be empty)")
            continue
        unknown = [t for t in tags if t not in ALLOWED_ACTION_TAGS]
        if unknown:
            errors.append(
                f"{prefix}: unknown tags {unknown}; allowed: "
                f"{sorted(ALLOWED_ACTION_TAGS)}"
            )
    return errors


def validate_seed(seed: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for record in seed:
        record_errors = validate_record(record)
        errors.extend(record_errors)
        rid = record.get("id")
        if rid:
            if rid in seen_ids:
                errors.append(f"{rid}: duplicate id")
            seen_ids.add(rid)
    return errors
