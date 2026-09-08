"""
scripts/load_toast_order_data_to_neon.py

Upserts the processed Toast item-sales and order/check-level CSVs into their
Neon tables.
Reads the CSVs written by scripts/process_orders_to_df.py.

Environment variables:
    ORDERS_OUTPUT_DIR       Folder containing item_sales.csv and
                             toast_order_checks.csv.
                             Defaults to raw_orders (repo-root relative) --
                             matches process_orders_to_df.py's default.
    NEON_CONNECTION_STRING  Required. Neon Postgres connection string.
"""

import os
import pandas as pd
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import db_neon #type:ignore
from schemas import TOAST_ITEM_SALES, TOAST_ORDER_CHECKS  # type: ignore

ORDERS_MAP = {"item_sales": {"csv": "item_sales.csv",
                             "key_columns": ["selection_guid"],
                             "schema": TOAST_ITEM_SALES,},
              "toast_order_checks": {"csv": "toast_order_checks.csv",
                                     "key_columns": ["check_guid"],
                                     "schema": TOAST_ORDER_CHECKS,}}

def main() -> None:
    orders_dir = os.environ.get("ORDERS_OUTPUT_DIR", str(REPO_ROOT / "raw_orders"))
    engine = db_neon.get_neon_engine()

    for table_name, config in ORDERS_MAP.items():
        csv_path = os.path.join(orders_dir, config["csv"])
        if not os.path.exists(csv_path):
            print(f"[{table_name}] SKIPPED: {csv_path} not found.")
            continue
        df = pd.read_csv(csv_path)
        df = db_neon.enforce_schema(df, config["schema"])

        db_neon.upsert_table(engine=engine,
                             table_name=table_name,
                             df=df,
                             key_columns=config["key_columns"],
                             )

    print("\nCHECKPOINT: Toast item sales and order checks Neon upsert complete.")

if __name__ == "__main__":
    main()