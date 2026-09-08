"""
Turns the JSON files saved by scripts/run_labor_extraction_api.py into a single
time-entry-level DataFrame (one row per time entry, wage-complemented via the
jobs catalog), and writes it out as CSV for debugging/inspection in the
GitHub Actions run.

Environment variables:
    LABOR_YEAR_DIRS     Comma-separated list of year folders to process,
                        e.g. "raw_labor/2026" or "raw_labor/2025, raw_labor/2026".
                        Defaults to the single year folder implied by START_YEAR
                        (same env var used by run_labor_extraction_api.py), so by
                        default this processes whatever the extraction step
                        that just ran produced.
    CSV_OUTPUT_PATH     Where to write the resulting CSV.
                        Defaults to raw_labor/labor_time_entries.csv (repo-root relative).
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_toast_labor as labor_processing # type: ignore


def main() -> None:
    start_year = os.environ.get("START_YEAR", "2026")

    default_labor_year_dir = str(REPO_ROOT / "raw_labor" / start_year)
    year_labor_dirs_raw = os.environ.get("LABOR_YEAR_DIRS", default_labor_year_dir)
    year_labor_dirs = [p.strip() for p in year_labor_dirs_raw.split(",") if p.strip()]

    for dir in year_labor_dirs:
        if not os.path.isdir(dir):
            print(f"ERROR: '{dir}' is not a directory (check LABOR_YEAR_DIRS / START_YEAR).", file=sys.stderr)
            sys.exit(1)

    default_csv_path = str(REPO_ROOT / "raw_labor" / "labor_time_entries.csv")
    csv_output_path = os.environ.get("CSV_OUTPUT_PATH", default_csv_path)
    os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)

    jobs_json_path = str(REPO_ROOT / "catalogs" / "catalog_jobs.json")

    print(f"Processing year dirs: {year_labor_dirs}")
    print(f"CSV output: {csv_output_path}")
    print(f"Jobs catalog: {jobs_json_path}")

    df = labor_processing.build_labor_dataframes(years_labor_dirs=year_labor_dirs,
                                                 output_dir=csv_output_path,
                                                 jobs_filepath=jobs_json_path,
                                                )
    print(f"\nLabor CHECKPOINT: {len(df)} time-entry-level rows built.")


if __name__ == "__main__":
    main()