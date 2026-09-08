"""
scripts/process_marginedge_catalogs_to_df.py

Turns raw MarginEdge catalog JSON into CSV dimension tables.

Environment variables:
    MARGINEDGE_CATALOG_INPUT_DIR   Defaults to catalogs/marginedge (repo-root relative) --
                                    matches run_marginedge_catalog_extraction_api.py's default.
    MARGINEDGE_CATALOG_OUTPUT_DIR  Defaults to the same as the input dir.
"""

import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_purchaise_orders as me_processing # type: ignore

CATALOG_BUILDERS = {
    "restaurant_units": me_processing.build_dataframe_from_json_restaurant_units,
    "vendors": me_processing.build_dataframe_from_json_vendors,
    "categories": me_processing.build_dataframe_from_json_categories,
}


def main() -> None:
    input_dir = os.environ.get("MARGINEDGE_CATALOG_INPUT_DIR", str(REPO_ROOT / "catalogs" / "marginedge"))
    output_dir = os.environ.get("MARGINEDGE_CATALOG_OUTPUT_DIR", input_dir)

    if not os.path.isdir(input_dir):
        print(f"ERROR: '{input_dir}' is not a directory (check MARGINEDGE_CATALOG_INPUT_DIR).", file=sys.stderr)
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

        builder(json_path, csv_path)
        row_count = len(pd.read_csv(csv_path))
        print(f"[{catalog_type}] {row_count} rows -> {csv_path}")

    print("\nCHECKPOINT: MarginEdge catalog CSV conversion complete.")


if __name__ == "__main__":
    main()