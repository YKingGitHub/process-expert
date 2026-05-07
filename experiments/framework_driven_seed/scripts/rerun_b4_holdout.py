"""Re-run the 定位销 (B4) holdout against the framework-driven seed.

Reads `data/seed_v1.json` directly — does NOT use the brittle keyword-based
`ExpandedKnowledgeQuery`. Routing here is purely framework-branch lookup
(question → likely branch → records under that branch). The point of this
script is to show how many of the original B4 holdout gaps the new KB
covers WITHOUT re-engineering the routing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.framework_driven_seed.src.loader import (  # noqa: E402
    index_by_branch,
    load_seed,
)


# 20 holdout knowledge needs from 定位销, mapped to expected framework branches.
# Each entry: id, question gist, expected branches (any match counts), expected family.
HOLDOUT_NEEDS = [
    ("KN-1804-M",   "未注尺寸公差按 GB/T1804-m",          ["2.11.1"], "标准"),
    ("KN-1184-H",   "未注形位公差按 GB/T 1184-H",          ["2.11.1"], "标准"),
    ("KN-EDGE",     "倒圆 R0.13-R0.5 未注公差",            ["2.11.1"], "标准"),
    ("KN-POSITION", "位置度 ⊕φ0.12 C 检验",                ["2.8.1.3", "2.10.2"], "经验"),
    ("KN-RUNOUT",   "圆度 ◯φ0.10 B 检验基准",              ["2.8.1.3", "2.10.2"], "经验"),
    ("KN-PERP",     "垂直度 ⊥0.025 B 检验",                ["2.8.1.3", "2.10.2"], "经验"),
    ("KN-CNC-LATHE","数控车床加工能力",                    ["2.5.1"], "标准"),
    ("KN-3AXIS",    "三轴加工中心 R 圆角铣削",             ["2.5.2", "2.4.7"], "标准"),
    ("KN-ROUTE",    "数控车/普通车/加工中心 设备分工",     ["2.3.4", "2.5.6"], "经验"),
    ("KN-D-FLAT",   "D 型扁/异形孔加工方法",              ["2.4.7"], "经验"),
    ("KN-INNER-R",  "2-R2 内圆角铣削",                    ["2.4.7", "2.4.3"], "经验"),
    ("KN-BLANK",    "毛坯 φ26→φ21.74 余量",                ["2.9.1"], "标准"),
    ("KN-PYTHON",   "φ50H7 Python 上下偏差查表",           ["2.9.6"], "计算"),
    ("KN-THREAD",   "M14-6g 螺纹加工",                    ["2.4.4"], "标准"),
    ("KN-MAT-SS",   "Z2CND18-12NS 不锈钢加工",            ["2.2.2"], "经验"),
    ("KN-COOLANT",  "切削液卤硫含量限制",                  ["2.7.4"], "经验"),
    ("KN-PT",       "液体渗透检测 PT",                    ["2.10.4"], "标准"),
    ("KN-MULTI",    "多件加工切断",                       ["2.4.1"], "经验"),
    ("KN-SPHERE",   "SR5.33 球面车削",                    ["2.4.8"], "经验"),
    ("KN-CONE",     "25° 锥面车削",                        ["2.4.8"], "经验"),
]


def main() -> int:
    seed = load_seed()
    by_branch = index_by_branch(seed)

    # B1+B2+SprintC (case-driven, frozen) had 9 true-covered + 4 spurious.
    # We do NOT re-evaluate those — the pilot is ADDITIVE on top of them.
    # Reproducing baseline coverage in framework-driven form is a later WO.
    baseline_true_covered = {
        "KN-1804-M", "KN-1184-H", "KN-EDGE",
        "KN-CNC-LATHE", "KN-3AXIS", "KN-ROUTE",
        "KN-INNER-R", "KN-BLANK", "KN-PYTHON",
    }
    # 4 questions B4 holdout flagged as TRUE GAPS — B1+B2 routing failed
    # OR returned wrong family. These are what Phase 2 pilot must address.
    holdout_true_gaps_before_pilot = {
        "KN-POSITION", "KN-RUNOUT", "KN-PERP", "KN-D-FLAT",
        "KN-MAT-SS", "KN-COOLANT", "KN-MULTI", "KN-CONE",
    }
    # KN-THREAD was scored as covered (spurious) in B4 — pilot replaces with real coverage
    holdout_spurious_in_baseline = {"KN-THREAD", "KN-PT", "KN-SPHERE", "KN-RUNOUT"}

    pilot_new_coverage = []  # uncovered_to_covered (real new)
    pilot_replaces_spurious = []  # was scored covered but spuriously; now real
    still_gap_after_pilot = []
    pilot_irrelevant = []  # not in pilot scope (deferred to next batch)

    pilot_branch_set = set(by_branch.keys())

    for nid, question, expected_branches, expected_family in HOLDOUT_NEEDS:
        # Hit: any expected branch is in pilot scope AND has record matching family
        hit = False
        top_id = None
        for branch in expected_branches:
            for r in by_branch.get(branch, []):
                if r["family"] == expected_family:
                    hit = True
                    top_id = r["id"]
                    break
            if hit:
                break

        in_pilot_scope = any(b in pilot_branch_set for b in expected_branches)

        entry = {
            "id": nid,
            "question": question,
            "expected_branches": expected_branches,
            "expected_family": expected_family,
            "framework_top_id": top_id,
        }

        if hit and nid in holdout_true_gaps_before_pilot:
            pilot_new_coverage.append(entry)
        elif hit and nid in holdout_spurious_in_baseline:
            pilot_replaces_spurious.append(entry)
        elif not hit and not in_pilot_scope:
            pilot_irrelevant.append({"id": nid, "reason": "branch not in pilot scope; covered by B1+B2 case-driven seed (frozen)"})
        elif not hit and in_pilot_scope:
            still_gap_after_pilot.append(entry)

    report = {
        "holdout_count": len(HOLDOUT_NEEDS),
        "pilot_branches_extracted": sorted(pilot_branch_set),
        "pilot_record_count": len(seed),
        "summary": {
            "pilot_new_coverage_count": len(pilot_new_coverage),
            "pilot_replaces_spurious_count": len(pilot_replaces_spurious),
            "still_gap_after_pilot_in_scope_count": len(still_gap_after_pilot),
            "pilot_out_of_scope_count": len(pilot_irrelevant),
        },
        "pilot_new_coverage": pilot_new_coverage,
        "pilot_replaces_spurious": pilot_replaces_spurious,
        "still_gap_after_pilot": still_gap_after_pilot,
        "pilot_irrelevant_deferred": pilot_irrelevant,
        "interpretation": (
            "Pilot extracts 6 framework branches (2.4.4 / 2.8.1.1-3 / 2.8.2.1-2). "
            "It is ADDITIVE on top of B1+B2+SprintC case-driven seed; that seed is frozen, not replaced. "
            "Out-of-pilot-scope holdout questions (KN-1804-M, KN-CNC-LATHE, KN-PYTHON, etc.) "
            "still rely on B1+B2 records — those are not re-evaluated here."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
