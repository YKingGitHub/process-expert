# Knowledge Capability Evaluation Baseline

This experiment turns the real-drawing gap findings into a reusable capability
baseline.

It does not call live VLM or LLM services. It uses the checked-in
`agent_query_eval` source-backed seed and a fixed question set to answer:

```text
Which general process-planning capabilities are already supported?
Which capability gaps remain before process-card generation?
Can the real drawing gaps be mapped to those general capabilities?
```

## Capability Set

The baseline covers 7 capabilities, with at least 3 questions per capability:

| Capability | Purpose |
| --- | --- |
| `drawing_requirement_interpretation` | Interpret drawing notes, standard clauses, and requirement symbols. |
| `geometric_tolerance_inspection` | Explain and inspect position, symmetry, and datum-related tolerances. |
| `equipment_operation_capability` | Match available machines to operations and limits. |
| `feature_process_selection` | Select process families for D-shaped holes, keyslots, radii, and non-round features. |
| `machining_allowance_planning` | Plan blank-to-finished and finish-to-grind allowances. |
| `route_planning` | Use principles and cases to organize process route families. |
| `deterministic_calculation` | Identify calculations that must be executed by deterministic Python. |

## Run

```bash
python3 experiments/knowledge_capability_eval/scripts/evaluate.py
python3 -m pytest experiments/knowledge_capability_eval/tests -q
```

The script writes:

```text
experiments/knowledge_capability_eval/output/knowledge_capability_eval_report.json
```

## Acceptance Criteria

- AC1: at least 7 capabilities.
- AC2: at least 3 questions per capability.
- AC3: every question has `expected_family`, `expected_subtype`, and `expected_contract`.
- AC4: report includes `gap_count_by_capability`.
- AC5: real drawing gaps map back to these capabilities.

