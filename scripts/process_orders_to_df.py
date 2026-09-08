"""
Turns the JSON files saved by scripts/run_order_extraction.py into a single
item-level DataFrame (one row per item sold), and writes it out as CSV for
debugging/inspection in the GitHub Actions run.

Environment variables:
    ORDERS_YEAR_DIRS   Comma-separated list of year folders to process,
                        e.g. "raw_orders/2026" or "raw_orders/2025,raw_orders/2026".
                        Defaults to the single year folder implied by START_YEAR
                        (same env var used by run_order_extraction.py), so by
                        default this processes whatever the extraction step
                        that just ran produced.
    CSV_OUTPUT_PATH    Where to write the resulting CSV.
                        Defaults to raw_orders/item_sales_per_day.csv (repo-root relative).
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_toast_order as order_processing  # type: ignore


def main() -> None:
    start_year = os.environ.get("START_YEAR", "2026")

    default_orders_year_dir = str(REPO_ROOT / "raw_orders" / start_year)
    year_order_dirs_raw = os.environ.get("ORDERS_YEAR_DIRS", default_orders_year_dir)
    year_order_dirs = [p.strip() for p in year_order_dirs_raw.split(",") if p.strip()]

    for dir in year_order_dirs:
        if not os.path.isdir(dir):
            print(f"ERROR: '{dir}' is not a directory (check ORDERS_YEAR_DIRS / START_YEAR).", file=sys.stderr)
            sys.exit(1)

    orders_csv_path = str(REPO_ROOT / "raw_orders" / "toast_order_checks.csv")
    orders_csv_output_path = os.environ.get("CSV_OUTPUT_PATH", orders_csv_path)
    os.makedirs(os.path.dirname(orders_csv_output_path), exist_ok=True)

    items_sales_csv_path = str(REPO_ROOT / "raw_orders" / "item_sales.csv")
    item_sales_csv_output_path = os.environ.get("CSV_OUTPUT_PATH", items_sales_csv_path)
    os.makedirs(os.path.dirname(item_sales_csv_output_path), exist_ok=True)
    

    print(f"Processing year dirs: {year_order_dirs}")
    print(f"CSV output: {orders_csv_output_path} and {item_sales_csv_output_path}")
    order_processing.build_item_and_order_dataframes(orders_years_dirs=year_order_dirs, 
                                                     order_checks_output_dir=orders_csv_path,
                                                     items_output_dir=item_sales_csv_output_path)


    sales_by_hour_csv_path = str(REPO_ROOT / "raw_orders" / "sales_by_hour.csv")
    sales_by_hour_csv_output_path = os.environ.get("CSV_OUTPUT_PATH", sales_by_hour_csv_path)
    os.makedirs(os.path.dirname(sales_by_hour_csv_output_path), exist_ok=True)
    print(f"Processing year dirs: {year_order_dirs}")
    print(f"CSV output: {sales_by_hour_csv_output_path}")
    order_processing.build_hourly_sales_dataframe(year_order_dirs, sales_by_hour_csv_output_path)


if __name__ == "__main__":
    main()
