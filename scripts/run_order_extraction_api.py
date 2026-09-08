"""
Runner for Toast order extraction, driven entirely by environment variables
so it can run unattended in GitHub Actions.

Required environment variables:
    TOAST_HOSTNAME          e.g. ws-api.toasttab.com
    TOAST_CLIENT_ID
    TOAST_CLIENT_SECRET
    TOAST_RESTAURANT_GUID
    NEON_CONNECTION_STRING  used to auto-resume from the last loaded date when
                            START_YEAR isn't set (scheduled runs)

Optional:
    START_YEAR/START_MONTH/START_DAY, END_YEAR/END_MONTH/END_DAY
        Manual override (e.g. a workflow_dispatch run or local backfill).
        START_DAY defaults to 1; END_DAY defaults to that month's last day --
        so a plain START_YEAR/START_MONTH still pulls the whole month, same
        as before day-level extraction was added.
    OUTPUT_DIR   (default: raw_orders/<start year>)

    If START_YEAR is NOT set at all (a scheduled run with no manual inputs),
    this resumes from the day after the most recent date already loaded into
    toast_order_checks in Neon, through today.

Never print CLIENT_SECRET or ACCESS_TOKEN values anywhere in this script.
GitHub Actions redacts registered secrets from logs, but only exact-string
matches; a partial copy (e.g. a JWT containing the secret) would not be caught.
"""

import os
import sys
import json
import glob
import calendar
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import api_toast as toast # type: ignore
import db_neon # type: ignore


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


def _resolve_date_range(table_name: str, earliest_fallback: tuple = (2023, 5, 1)) -> tuple[tuple, tuple]:
    """
    Resolves (start_date, end_date) as (year, month, day) tuples.

    START_YEAR set: builds start_date from START_YEAR/MONTH/DAY (day defaults to 1).
    START_YEAR not set: resumes from the day after the most recent date already
    loaded into table_name in Neon -- self-healing if a run is missed or fails,
    since it always resumes from Neon's actual state rather than a fixed range.

    END_YEAR set: builds end_date from END_YEAR/MONTH/DAY (month defaults to
    12, day defaults to that month's last day).
    END_YEAR not set: defaults to today.

    Start and end are resolved independently, so you can mix e.g. an explicit
    end_date with an auto-resumed start_date (leave start blank, cap end).
    """
    if os.environ.get("START_YEAR"):
        start_year = int(os.environ["START_YEAR"])
        start_month = int(os.environ.get("START_MONTH", 1))
        start_day = int(os.environ.get("START_DAY", 1))
        start_date = (start_year, start_month, start_day)
    else:
        engine = db_neon.get_neon_engine()
        last_date = db_neon.get_last_extracted_date(engine, table_name)
        start_date = earliest_fallback if last_date is None else _next_day(last_date)

    if os.environ.get("END_YEAR"):
        end_year = int(os.environ["END_YEAR"])
        end_month = int(os.environ.get("END_MONTH", 12))
        default_end_day = calendar.monthrange(end_year, end_month)[1]
        end_day = int(os.environ.get("END_DAY", default_end_day))
        end_date = (end_year, end_month, end_day)
    else:
        today = date.today()
        end_date = (today.year, today.month, today.day)

    return start_date, end_date


def _next_day(d: date) -> tuple:
    nxt = d + timedelta(days=1)
    return (nxt.year, nxt.month, nxt.day)


def main() -> None:
    toast_hostname = _require_env("TOAST_HOSTNAME").replace("https://", "").replace("http://", "").rstrip("/")
    client_id = _require_env("TOAST_CLIENT_ID")
    client_secret = _require_env("TOAST_CLIENT_SECRET")
    restaurant_guid = _require_env("TOAST_RESTAURANT_GUID")

    start_date, end_date = _resolve_date_range("toast_order_checks")

    output_dir = os.environ.get("OUTPUT_DIR", os.path.join("raw_orders", str(start_date[0])))

    print(f"Running Toast order extraction: {start_date} -> {end_date}")
    print(f"Output dir: {output_dir}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"output_dir={output_dir}\n")

    toast.run_order_extraction(
        toast_hostname=toast_hostname,
        client_id=client_id,
        client_secret=client_secret,
        restaurant_guid=restaurant_guid,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
    )

    #### Checkpoint: confirm the JSON was actually written and show a quick preview, without ever touching/printing credentials or tokens.
    order_files = sorted(glob.glob(os.path.join(output_dir, "orders_*.json")))

    if not order_files:
        print(f"\nCHECKPOINT: no orders_*.json files found in {output_dir} "
              f"(extraction may have failed -- check logs above).")
        return

    total_orders = 0
    for path in order_files:
        with open(path, "r", encoding="utf-8") as f:
            orders = json.load(f)
        total_orders += len(orders)
        print(f"\nCHECKPOINT [{os.path.basename(path)}]: {len(orders)} orders saved.")

    print(f"\nCHECKPOINT TOTAL: {len(order_files)} file(s), {total_orders} orders across the range.")
    with open(order_files[0], "r", encoding="utf-8") as f:
        orders = json.load(f)
    if orders:
        print("\nFirst order (preview):")
        print(json.dumps(orders[0], indent=2)[:1500])


if __name__ == "__main__":
    main()
