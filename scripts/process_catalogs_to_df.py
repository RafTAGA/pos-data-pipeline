"""
Turns the raw catalog JSON files saved by scripts/run_catalog_extraction_api.py
into readable CSV dimension tables (GUID -> name mappings), one CSV per catalog.

Each builder function in json_processing_toast_catalog_extraction.py now
writes its own CSV directly (takes filepath + output_file, returns None) --
this script does not build or write CSVs itself, it just calls each builder
with the right paths and reports back what was written.

Lives in scripts/, imports json_processing_toast_catalog_extraction from ../modules/.

Note: menu_groups is intentionally NOT processed here -- CATALOGS in
api_toast.py doesn't currently fetch a menuGroups endpoint, so there's no
catalog_menu_groups.json for build_dataframe_from_json_menu_groups() to read.

Environment variables:
    CATALOG_INPUT_DIR   Folder containing the raw catalog_*.json files.
                        Defaults to catalogs (repo-root relative) -- matches
                        run_catalog_extraction_api.py's default output dir.
    CATALOG_OUTPUT_DIR  Folder to write the resulting catalog_*.csv files into.
                        Defaults to the same as CATALOG_INPUT_DIR.
"""

import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_toast_catalog_extraction as catalogs

CATALOG_BUILDERS = {
    "sales_categories": catalogs.build_dataframe_from_json_sales_category,
    "revenue_centers": catalogs.build_dataframe_from_json_revenue_centers,
    "dining_options": catalogs.build_dataframe_from_json_dining_option,
    "tables": catalogs.build_dataframe_tables,
    "menu_items": catalogs.build_dataframe_from_json_menu_items,
    "employees": catalogs.build_dataframe_from_json_employees,
    "jobs": catalogs.build_dataframe_from_json_jobs,
}


def main() -> None:
    input_dir = os.environ.get("CATALOG_INPUT_DIR", str(REPO_ROOT / "catalogs"))
    output_dir = os.environ.get("CATALOG_OUTPUT_DIR", input_dir)

    if not os.path.isdir(input_dir):
        print(f"ERROR: '{input_dir}' is not a directory (check CATALOG_INPUT_DIR).", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"Input dir: {input_dir}")
    print(f"Output dir: {output_dir}")

    for catalog_type, builder in CATALOG_BUILDERS.items():
        json_path = os.path.join(input_dir, f"catalog_{catalog_type}.json")
        csv_path = os.path.join(output_dir, f"catalog_{catalog_type}.csv")

        if not os.path.exists(json_path):
            print(f"[{catalog_type}] SKIPPED: {json_path} not found.")
            continue

        # Builder writes the CSV itself and returns None -- read row count
        # back from the CSV it just wrote, purely for the checkpoint print.
        builder(json_path, csv_path)
        row_count = len(pd.read_csv(csv_path))
        print(f"[{catalog_type}] {row_count} rows -> {csv_path}")

    print("\nCHECKPOINT: catalog CSV conversion complete.")


if __name__ == "__main__":
    main()