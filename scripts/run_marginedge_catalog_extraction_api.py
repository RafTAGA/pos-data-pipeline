"""
scripts/run_marginedge_catalog_extraction_api.py

Runner for MarginEdge catalog (restaurant units, vendors, categories)
extraction, driven entirely by environment variables.

Required environment variables:
    MARGINEDGE_API_KEY
    MARGINEDGE_RESTAURANT_UNIT_ID

Optional:
    OUTPUT_DIR   (default: catalogs/marginedge)

Never print MARGINEDGE_API_KEY anywhere in this script.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import api_marginedge as marginedge # type: ignore


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: required environment variable '{name}' is not set.", file=sys.stderr)
        sys.exit(1)
    return value.strip()


def main() -> None:
    api_key = _require_env("MARGINEDGE_API_KEY")
    restaurant_unit_id = _require_env("MARGINEDGE_RESTAURANT_UNIT_ID")

    default_output_dir = REPO_ROOT / "catalogs" / "marginedge"
    output_dir = os.environ.get("OUTPUT_DIR", str(default_output_dir))

    print(f"Running MarginEdge catalog extraction.")
    print(f"Output dir: {output_dir}")

    marginedge.run_marginedge_catalog_extraction(
                                                 api_key=api_key,
                                                 restaurant_unit_id=restaurant_unit_id,
                                                 output_dir=output_dir,
                                                )

    if os.path.isdir(output_dir):
        files = sorted(f for f in os.listdir(output_dir) if f.endswith(".json"))
        print(f"\nCHECKPOINT: {len(files)} catalog file(s) in {output_dir}: {files}")
    else:
        print(f"\nCHECKPOINT: output dir {output_dir} not found (extraction may have failed).")


if __name__ == "__main__":
    main()