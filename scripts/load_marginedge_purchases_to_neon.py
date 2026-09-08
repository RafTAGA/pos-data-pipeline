"""
scripts/load_marginedge_purchases_to_neon.py

Upserts processed MarginEdge order and line-item CSVs into Neon.
Reads CSVs written by scripts/process_marginedge_purchaises_to_df.py.

Environment variables:
    MARGINEDGE_ORDERS_OUTPUT_DIR  Folder containing marginedge_orders.csv
                                    and marginedge_line_items.csv.
    NEON_CONNECTION_STRING         Required. Neon Postgres connection string.
"""

import os
import pandas as pd
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import db_neon  # type: ignore
from schemas import MARGINEDGE_ORDERS_SCHEMA, MARGINEDGE_LINE_ITEMS_SCHEMA  # type: ignore

UPSERT_MAP = {"marginedge_orders": {"csv": "marginedge_orders.csv",
                                    "key_columns": ["order_id"],
                                    "schema": MARGINEDGE_ORDERS_SCHEMA,
                                    },
              "marginedge_line_items": {"csv": "marginedge_line_items.csv",
                                        "key_columns": ["order_id", "line_item_index"],
                                        "schema": MARGINEDGE_LINE_ITEMS_SCHEMA,
                                        },
             }

def main() -> None:

    input_dir = os.environ.get("MARGINEDGE_ORDERS_OUTPUT_DIR", str(REPO_ROOT / "raw_marginedge"))

    engine = db_neon.get_neon_engine()

    for table_name, config in UPSERT_MAP.items():
        csv_path = os.path.join(input_dir, config["csv"])
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

    print("\nCHECKPOINT: MarginEdge purchases Neon upsert complete.")

if __name__ == "__main__":
    main()