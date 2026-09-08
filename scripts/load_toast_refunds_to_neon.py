"""
scripts/load_toast_refunds_to_neon.py

Upserts the processed Toast refunds CSV into its Neon table.
Reads the CSV written by scripts/process_refunds_to_df.py.

Environment variables:
    REFUNDS_OUTPUT_DIR      Folder containing refunds_daily_summary.csv.
                             Defaults to raw_refunds (repo-root relative) --
                             matches process_refunds_to_df.py's default.
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
from schemas import TOAST_REFUND_DAILY_SUMMARY  # type: ignore

REFUND_MAP = {"refunds_daily_summary": {"csv": "refunds_daily_summary.csv",
                                       "key_columns": ["guid"],
                                       "schema": TOAST_REFUND_DAILY_SUMMARY,}}

def main() -> None:
    refunds_dir = os.environ.get("REFUNDS_OUTPUT_DIR", str(REPO_ROOT / "raw_refunds"))
    engine = db_neon.get_neon_engine()

    for table_name, config in REFUND_MAP.items():
        csv_path = os.path.join(refunds_dir, config["csv"])
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

    print("\nCHECKPOINT: Toast refunds Neon upsert complete.")

if __name__ == "__main__":
    main()