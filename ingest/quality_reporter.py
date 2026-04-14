"""Quality reporter — generates summary statistics and writes quality report files."""

import json
import os
from datetime import datetime


class QualityReporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def report(self, stats: dict, db_path: str = None) -> dict:
        total = stats.get("total_pages", 0)
        t1 = stats.get("tier1_success", 0)
        t2 = stats.get("tier2_success", 0)
        t3 = stats.get("tier3_success", 0)
        unresolved = stats.get("unresolved", 0)
        skipped = stats.get("skipped_plain_text", 0)

        processed = t1 + t2 + t3 + unresolved
        cv_pass_rate = (t1 + t2) / max(processed, 1)
        unresolved_rate = unresolved / max(total, 1)

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_pages": total,
            "processed_pages": processed,
            "skipped_plain_text_pages": skipped,
            "tier1_success": t1,
            "tier2_success": t2,
            "tier3_vlm_success": t3,
            "unresolved_count": unresolved,
            "cross_validation_pass_rate": round(cv_pass_rate, 4),
            "vlm_fallback_count": t3,
            "unresolved_rate": round(unresolved_rate, 4),
        }

        # Optional: read DB counts for context
        if db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(db_path)
                report["total_process_params"] = conn.execute(
                    "SELECT COUNT(*) FROM process_params "
                    "WHERE extraction_method IN ('llm_extracted','vlm_fallback')"
                ).fetchone()[0]
                report["llm_extracted_count"] = conn.execute(
                    "SELECT COUNT(*) FROM process_params "
                    "WHERE extraction_method='llm_extracted'"
                ).fetchone()[0]
                conn.close()
            except Exception as e:
                report["db_stats_error"] = str(e)

        # stdout summary
        print("\n" + "=" * 60)
        print("质量报告")
        print("=" * 60)
        for k, v in report.items():
            print(f"  {k}: {v}")
        print("=" * 60 + "\n")

        # Write JSON file
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self.output_dir, f"quality_report_{ts}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"质量报告已写入: {out_path}")

        return report
