"""
scripts/load_catalogs_to_neon.py

Loads processed Toast catalog CSVs into their matching Neon tables.
Reads CSVs written by scripts/process_catalogs_to_df.py.

Environment variables:
    CATALOG_OUTPUT_DIR      Folder containing the catalog_*.csv files.
                             Defaults to catalogs (repo-root relative) --
                             matches process_catalogs_to_df.py's default.
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
from schemas import TOAST_CATALOG_TABLES, TOAST_CATALOG_DINING_OPTIONS, TOAST_CATALOG_MENU_ITEMS, TOAST_CATALOG_REVENUE_CENTERS, TOAST_CATALOG_SALES_CATEGORIES  # type: ignore



CATALOG_TABLE_MAP = {"catalog_tables": {'csv': "catalog_tables.csv",
                                        "schema": TOAST_CATALOG_TABLES},
                     "catalog_dining_options": {'csv': "catalog_dining_options.csv",
                                                "schema": TOAST_CATALOG_DINING_OPTIONS},
                     "catalog_menu_items": {'csv': "catalog_menu_items.csv",
                                            "schema": TOAST_CATALOG_MENU_ITEMS},
                     "catalog_revenue_centers": {'csv': "catalog_revenue_centers.csv",
                                                 "schema": TOAST_CATALOG_REVENUE_CENTERS},
                     "catalog_sales_categories": {'csv': "catalog_sales_categories.csv",
                                                  "schema": TOAST_CATALOG_SALES_CATEGORIES}
                     }


def main() -> None:
    catalog_dir = os.environ.get("CATALOG_OUTPUT_DIR", str(REPO_ROOT / "catalogs"))
    engine = db_neon.get_neon_engine()
    table_to_df = {}

    for table_name, config in CATALOG_TABLE_MAP.items():
        csv_path = os.path.join(catalog_dir, config['csv'])
        if not os.path.exists(csv_path):
            print(f"[{table_name}] SKIPPED: {csv_path} not found.")
            continue

        df = pd.read_csv(csv_path)
        table_to_df[table_name] = db_neon.enforce_schema(df, config["schema"])

    results = db_neon.replace_catalog_tables(engine, table_to_df)
    print("\nCHECKPOINT: Toast catalog Neon load complete.")
    print(results)

if __name__ == "__main__":
    main()