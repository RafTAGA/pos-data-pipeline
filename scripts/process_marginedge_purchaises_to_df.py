"""
scripts/process_marginedge_purchaises_to_df.py

Turns the JSON files saved by run_marginedge_extraction_api.py into
order-level and line-item-level DataFrames, and writes both out as CSV.

Environment variables:
    MARGINEDGE_YEAR_DIRS   Comma-separated list of year folders to process,
                            e.g. "raw_marginedge/2025, raw_marginedge/2026".
                            Defaults to the single year folder implied by
                            START_YEAR (same env var used by the extraction
                            runner), so by default this processes whatever
                            the extraction step that just ran produced.
    ORDERS_CSV_PATH        Defaults to raw_marginedge/marginedge_orders.csv
    LINE_ITEMS_CSV_PATH    Defaults to raw_marginedge/marginedge_line_items.csv
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_purchaise_orders as me_processing # type: ignore



def main() -> None:
    start_year = os.environ.get("START_YEAR", "2026")

    default_year_dir = str(REPO_ROOT / "raw_marginedge" / start_year)
    year_dirs_raw = os.environ.get("MARGINEDGE_YEAR_DIRS", default_year_dir)
    year_dirs = [p.strip() for p in year_dirs_raw.split(",") if p.strip()]

    for dir in year_dirs:
        if not os.path.isdir(dir):
            print(f"ERROR: '{dir}' is not a directory (check MARGINEDGE_YEAR_DIRS / START_YEAR).", file=sys.stderr)
            sys.exit(1)

    orders_csv_path = os.environ.get("ORDERS_CSV_PATH", str(REPO_ROOT / "raw_marginedge" / "marginedge_orders.csv"))
    line_items_csv_path = os.environ.get("LINE_ITEMS_CSV_PATH", str(REPO_ROOT / "raw_marginedge" / "marginedge_line_items.csv"))
    os.makedirs(os.path.dirname(orders_csv_path), exist_ok=True)

    print(f"Processing year dirs: {year_dirs}")
    print(f"Orders CSV: {orders_csv_path}")
    print(f"Line items CSV: {line_items_csv_path}")

    me_processing.build_marginedge_dataframes(marginedge_dirs=year_dirs, 
                                                                         orders_output_path=orders_csv_path, 
                                                                         line_items_output_path=line_items_csv_path,
                                                                         )



if __name__ == "__main__":
    main()