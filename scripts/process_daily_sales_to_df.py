"""
Builds the daily sales summary (net_sales, number_of_orders, number_of_guests
per business date) by combining orders JSON with refunds JSON — net_sales is
reduced by that day's refund_amount + tip_refund_amount.

Lives in scripts/, imports both json_processing_toast_order and
json_processing_toast_refunds from ../module/.

Environment variables:
    ORDERS_YEAR_DIRS    Comma-separated list of order year folders.
                        Defaults to the single year folder implied by START_YEAR.
    REFUNDS_YEAR_DIRS   Comma-separated list of refund year folders.
                        Defaults to the single year folder implied by START_YEAR.
    CSV_OUTPUT_PATH     Where to write the resulting CSV.
                        Defaults to raw_orders/daily_sales.csv (repo-root relative).

IMPORTANT — year coverage: orders and refunds are read from independent year
lists. If ORDERS_YEAR_DIRS covers years that REFUNDS_YEAR_DIRS doesn't, this
script will still run (a left-join fills missing refund days with 0), but
net_sales for the uncovered years will silently assume zero refunds rather
than reflecting real numbers. This script prints a warning when the two year
lists don't match so that gap is visible rather than silent.
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))

import json_processing_toast_order as order_processing  
import json_processing_toast_refunds as refund_processing 


def _year_from_dir(path: str) -> str:
    """extraction of a trailing 4-digit year from a folder path."""
    match = re.search(r"(\d{4})/?$", path.rstrip("/"))
    return match.group(1) if match else path


def main() -> None:
    start_year = os.environ.get("START_YEAR", "2026")

    default_orders_dir = str(REPO_ROOT / "raw_orders" / start_year)
    orders_year_dirs = [p.strip() for p in os.environ.get("ORDERS_YEAR_DIRS", default_orders_dir).split(",") if p.strip()]

    default_refunds_dir = str(REPO_ROOT / "raw_refunds" / start_year)
    refunds_year_dirs = [p.strip() for p in os.environ.get("REFUNDS_YEAR_DIRS", default_refunds_dir).split(",") if p.strip()]

    for dir in orders_year_dirs + refunds_year_dirs:
        if not os.path.isdir(dir):
            print(f"ERROR: '{dir}' is not a directory (check ORDERS_YEAR_DIRS / REFUNDS_YEAR_DIRS / START_YEAR).", file=sys.stderr)
            sys.exit(1)

    # Coverage check: warn (don't fail) if the two year lists don't line up,
    # since a mismatch silently zero-fills refunds for the uncovered years.
    orders_years = {_year_from_dir(dir) for dir in orders_year_dirs}
    refunds_years = {_year_from_dir(dir) for dir in refunds_year_dirs}
    if orders_years != refunds_years:
        print(
            f"WARNING: orders year coverage {sorted(orders_years)} does not match "
            f"refunds year coverage {sorted(refunds_years)}. Net sales for any year "
            f"present in orders but not in refunds will assume $0 refunds for that "
            f"year, which may overstate net sales."
        )

    default_csv_path = str(REPO_ROOT / "raw_orders" / "daily_sales.csv")
    csv_output_path = os.environ.get("CSV_OUTPUT_PATH", default_csv_path)
    os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)

    print(f"Orders year dirs: {orders_year_dirs}")
    print(f"Refunds year dirs: {refunds_year_dirs}")
    print(f"Daily sales summary CSV output: {csv_output_path}")


    refunds_csv_path = str(REPO_ROOT / "raw_refunds" / "refunds_daily_summary.csv")
    refunds_df = refund_processing.build_refunds_dataframe(refunds_year_dirs, refunds_csv_path)
    df = order_processing.build_daily_sales_dataframe(orders_year_dirs, csv_output_path, refunds_df)

    print(f"\nCHECKPOINT: {len(df)} daily sales rows built.")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst 5 rows:")
    print(df.head(5).to_string())

if __name__ == "__main__":
    main()