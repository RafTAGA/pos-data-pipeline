"""
scripts/load_toast_labor_to_neon.py

Upserts the processed Toast labor time-entries CSV into its Neon table.
Reads the CSV written by scripts/process_labor_to_df.py.

Environment variables:
    LABOR_OUTPUT_DIR        Folder containing labor_time_entries.csv.
                             Defaults to raw_labor (repo-root relative) --
                             matches process_labor_to_df.py's default.
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
from schemas import TOAST_LABOR_TIME_ENTRIES  # type: ignore

LABOR_MAP = {"labor_time_entries": {"csv": "labor_time_entries.csv",
                                    "key_columns": ["time_entry_guid"],
                                    "schema": TOAST_LABOR_TIME_ENTRIES,}}

def main() -> None:
    labor_dir = os.environ.get("LABOR_OUTPUT_DIR", str(REPO_ROOT / "raw_labor"))
    engine = db_neon.get_neon_engine()

    for table_name, config in LABOR_MAP.items():
        csv_path = os.path.join(labor_dir, config["csv"])
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

    print("\nCHECKPOINT: Toast labor records Neon upsert complete.")

if __name__ == "__main__":
    main()