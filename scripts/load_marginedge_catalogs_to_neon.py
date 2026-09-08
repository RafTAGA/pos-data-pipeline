"""
scripts/load_marginedge_catalogs_to_neon.py

Loads processed MarginEdge catalog CSVs into their matching Neon tables.
Reads CSVs written by scripts/process_marginedge_catalogs_to_df.py.

Environment variables:
    MARGINEDGE_CATALOG_OUTPUT_DIR  Folder containing the catalog_*.csv files.
                                     Defaults to catalogs/marginedge --
                                     matches process_marginedge_catalogs_to_df.py's default.
    NEON_CONNECTION_STRING          Required. Neon Postgres connection string.
"""

import os
import pandas as pd
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import db_neon  # type: ignore
from schemas import MARGINEDGE_CATALOG_PURCHAISE_CATEGORIES, MARGINEDGE_CATALOG_VENDORS_SCHEMA  # type: ignore


CATALOG_TABLE_MAP = {
                     "catalog_purchase_categories": {"csv": "catalog_categories.csv",
                                                     "schema": MARGINEDGE_CATALOG_PURCHAISE_CATEGORIES,
                                                     },
                     "catalog_vendors": {"csv": "catalog_vendors.csv",
                                         "schema": MARGINEDGE_CATALOG_VENDORS_SCHEMA
                                         }
                    }


def main() -> None:
    catalog_dir = os.environ.get("MARGINEDGE_CATALOG_OUTPUT_DIR", str(REPO_ROOT / "catalogs" / "marginedge"))

    engine = db_neon.get_neon_engine()
    table_to_df = {}

    for table_name, config in CATALOG_TABLE_MAP.items():
        csv_path = os.path.join(catalog_dir, config['csv'])
        if not os.path.exists(csv_path):
            print(f"[{table_name}] SKIPPED: {csv_path} not found.")
            continue

        df = pd.read_csv(csv_path)
        table_to_df[table_name] = db_neon.enforce_schema(df, config["schema"])

    results = db_neon.replace_catalog_tables(engine=engine,
                                             table_to_df=table_to_df
                                             )
    print("\nCHECKPOINT: MarginEdge catalog Neon load complete.")
    print(results)


if __name__ == "__main__":
    main()