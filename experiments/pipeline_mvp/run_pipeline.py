"""Run the end-to-end pipeline on all checked-in input cases.

Usage:
  python3 run_pipeline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from process_calc.pipeline import plan_craft_card, render_markdown

CASES = ["textbook_locating_sleeve"]
INPUTS = REPO_ROOT / "experiments" / "pipeline_mvp" / "inputs"
OUTPUTS = REPO_ROOT / "experiments" / "pipeline_mvp" / "outputs"


def main():
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        in_path = INPUTS / f"{case}.json"
        with open(in_path, encoding="utf-8") as f:
            input_data = json.load(f)
        plan = plan_craft_card(input_data)
        md = render_markdown(plan)

        json_out = OUTPUTS / f"{case}.json"
        md_out = OUTPUTS / f"{case}.md"
        json_out.write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        md_out.write_text(md, encoding="utf-8")

        s = plan["summary"]
        print(f"=== {case} ===")
        print(f"  features={s['feature_count']}  ops={s['op_count']}  "
              f"kb_hit={s['kb_hit_rate']:.0%}  gaps={s['gap_count']}")
        if plan.get("divergence_notes"):
            for n in plan["divergence_notes"]:
                print(f"  ⚠️  {n}")


if __name__ == "__main__":
    main()
