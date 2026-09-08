"""
Turns the JSON files saved by scripts/run_refund_extraction.py into a daily
refunds summary DataFrame (one row per business date: total refund amount,
total tip refund amount), and writes it out as CSV for debugging/inspection
in the GitHub Actions run.

Lives in scripts/, imports json_processing_toast_refunds from ../module/.

Environment variables:
    REFUNDS_YEAR_DIRS  Comma-separated list of year folders to process,
                        e.g. "raw_refunds/2026" or "raw_refunds/2025,raw_refunds/2026".
                        Defaults to the single year folder implied by START_YEAR
                        (same env var used by run_refund_extraction.py), so by
                        default this processes whatever the extraction step
                        that just ran produced.
    CSV_OUTPUT_PATH    Where to write the resulting CSV.
                        Defaults to raw_refunds/refunds_daily_summary.csv (repo-root relative).
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_toast_refunds as refund_processing   # type: ignore


def main() -> None:
    start_year = os.environ.get("START_YEAR", "2026")

    default_year_dir = str(REPO_ROOT / "raw_refunds" / start_year)
    year_dirs_raw = os.environ.get("REFUNDS_YEAR_DIRS", default_year_dir)
    year_dirs = [p.strip() for p in year_dirs_raw.split(",") if p.strip()]

    for d in year_dirs:
        if not os.path.isdir(d):
            print(f"ERROR: '{d}' is not a directory (check REFUNDS_YEAR_DIRS / START_YEAR).", file=sys.stderr)
            sys.exit(1)

    default_csv_path = str(REPO_ROOT / "raw_refunds" / "refunds_daily_summary.csv")
    csv_output_path = os.environ.get("CSV_OUTPUT_PATH", default_csv_path)
    os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)
    print(f"Processing year dirs: {year_dirs}")
    print(f"CSV output: {csv_output_path}")
    df = refund_processing.build_refunds_dataframe(year_dirs, csv_output_path)
    print(f"\nDaily refunds CHECKPOINT: {len(df)} daily refund summary rows built.")

if __name__ == "__main__":
    main()