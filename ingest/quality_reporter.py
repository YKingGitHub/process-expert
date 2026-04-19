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

        tol_success = stats.get("tolerance_success", 0)
        tol_vlm = stats.get("tolerance_vlm", 0)
        surf_success = stats.get("surface_success", 0)

        processed = t1 + t2 + t3 + unresolved  # param_table pages only (excludes tolerance/surface)
        tier1_rate = t1 / max(processed, 1)
        overall_extraction_rate = (t1 + t2 + t3) / max(processed, 1)
        unresolved_rate = unresolved / max(processed, 1)
        vlm_dependency_rate = t3 / max(processed, 1)
        # Deprecated — kept for transition (was misnamed; actually = (t1+t2)/processed)
        cv_pass_rate_deprecated = (t1 + t2) / max(processed, 1)

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_pages": total,
            "param_table_pages": processed,
            "non_param_pages": skipped,
            "tier1_success": t1,
            "tier2_success": t2,
            "tier3_vlm_success": t3,
            "unresolved_count": unresolved,
            # Core metrics
            "tier1_rate": round(tier1_rate, 4),
            "overall_extraction_rate": round(overall_extraction_rate, 4),
            "unresolved_rate": round(unresolved_rate, 4),
            "vlm_dependency_rate": round(vlm_dependency_rate, 4),
            # Deprecated — kept for transition
            "cross_validation_pass_rate_DEPRECATED": round(cv_pass_rate_deprecated, 4),
            # Tolerance & surface stats
            "tolerance_success_pages": tol_success,
            "tolerance_vlm_pages": tol_vlm,
            "surface_success_pages": surf_success,
        }

        # Optional: read DB counts for context
        if db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(db_path)
                report["total_cutting_params"] = conn.execute(
                    "SELECT COUNT(*) FROM cutting_params "
                    "WHERE extraction_method IN ('llm_extracted','vlm_fallback')"
                ).fetchone()[0]
                report["llm_extracted_count"] = conn.execute(
                    "SELECT COUNT(*) FROM cutting_params "
                    "WHERE extraction_method='llm_extracted'"
                ).fetchone()[0]
                # Per-table row counts
                for tbl in ("cutting_params", "tolerance_fits", "equipment_specs", "surface_standards"):
                    try:
                        report[f"rows_{tbl}"] = conn.execute(
                            f"SELECT COUNT(*) FROM {tbl}"
                        ).fetchone()[0]
                    except Exception:
                        report[f"rows_{tbl}"] = "N/A"
                # Coverage: distinct pages with valid data / classified pages
                try:
                    tol_pages_with_data = conn.execute(
                        "SELECT COUNT(DISTINCT source_page) FROM tolerance_fits"
                    ).fetchone()[0]
                    tol_classified = stats.get("tolerance_success", 0) + stats.get("unresolved", 0)
                    report["tolerance_coverage"] = round(tol_pages_with_data / max(tol_classified, 1), 4)
                except Exception:
                    report["tolerance_coverage"] = "N/A"
                try:
                    surf_pages_with_data = conn.execute(
                        "SELECT COUNT(DISTINCT source_page) FROM surface_standards"
                    ).fetchone()[0]
                    surf_classified = stats.get("surface_success", 0)
                    report["surface_coverage"] = round(surf_pages_with_data / max(surf_classified, 1), 4)
                except Exception:
                    report["surface_coverage"] = "N/A"
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
