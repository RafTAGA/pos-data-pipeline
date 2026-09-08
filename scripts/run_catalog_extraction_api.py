"""
Runner for Toast catalog extraction, driven entirely by environment variables
so it can run unattended in GitHub Actions.

Required environment variables:
    TOAST_HOSTNAME          e.g. ws-api.toasttab.com
    TOAST_CLIENT_ID
    TOAST_CLIENT_SECRET
    TOAST_RESTAURANT_GUID

Optional (all default to a single-month June 2026 checkpoint run):
    START_YEAR   (default: 2026)
    START_MONTH  (default: 6)
    END_YEAR     (default: 2026)
    END_MONTH    (default: 6)
    OUTPUT_DIR   (default: raw_orders/<year>)

Never print CLIENT_SECRET or ACCESS_TOKEN values anywhere in this script.
GitHub Actions redacts registered secrets from logs, but only exact-string
matches; a partial copy (e.g. a JWT containing the secret) would not be caught.
"""

import os
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import api_toast as toast # type: ignore


def _require_env(name: str) -> str:
    """
    Retrieve the secret from github, stripping blanks
    Args:
        name: Secret Variable GitHub Name
    
    Returns:
        value: Secret Variable as stripped variable 
    """
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: required environment variable '{name}' is not set.", file=sys.stderr)
        sys.exit(1)
    return value.strip()


def main() -> None:
    toast_hostname = _require_env("TOAST_HOSTNAME").replace("https://", "").replace("http://", "").rstrip("/")
    client_id = _require_env("TOAST_CLIENT_ID")
    client_secret = _require_env("TOAST_CLIENT_SECRET")
    restaurant_guid = _require_env("TOAST_RESTAURANT_GUID")

    default_output_dir = REPO_ROOT / "catalogs"
    output_dir = os.environ.get("OUTPUT_DIR", str(default_output_dir))

    print(f"Running Toast catalog extraction.")
    print(f"Output dir: {output_dir}")

    toast.run_catalog_extraction(toast_hostname=toast_hostname, 
                                 client_id=client_id, 
                                 client_secret=client_secret, 
                                 output_dir=output_dir, 
                                 restaurant_guid=restaurant_guid,)

    # Checkpoint: confirm which catalog files actually landed, without ever
    # touching/printing credentials or tokens.
    if os.path.isdir(output_dir):
        files = sorted(f for f in os.listdir(output_dir) if f.endswith(".json"))
        print(f"\nCHECKPOINT: {len(files)} catalog file(s) in {output_dir}: {files}")
    else:
        print(f"\nCHECKPOINT: output dir {output_dir} not found (extraction may have failed).")

if __name__ == "__main__":
    main()