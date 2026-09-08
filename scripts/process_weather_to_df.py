"""
scripts/process_weather_to_df.py

Turns the flattened JSON files saved by run_weather_extraction_api.py into a
single daily weather DataFrame (yyyyMMdd-standardized), and writes it out as CSV.

Environment variables:
    WEATHER_YEAR_DIRS   Comma-separated list of year folders to process,
                         e.g. "raw_weather/2025, raw_weather/2026".
                         Defaults to the single year folder implied by
                         START_YEAR (same env var used by the extraction
                         runner), so by default this processes whatever the
                         extraction step that just ran produced.
    CSV_OUTPUT_PATH      Defaults to raw_weather/daily_weather.csv
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modules"
sys.path.insert(0, str(MODULE_DIR))
import json_processing_open_meteo as weather_processing # type: ignore


def main() -> None:
    start_year = os.environ.get("START_YEAR", "2026")

    default_year_dir = str(REPO_ROOT / "raw_weather" / start_year)
    year_dirs_raw = os.environ.get("WEATHER_YEAR_DIRS", default_year_dir)
    year_dirs = [p.strip() for p in year_dirs_raw.split(",") if p.strip()]

    for dir in year_dirs:
        if not os.path.isdir(dir):
            print(f"ERROR: '{dir}' is not a directory (check WEATHER_YEAR_DIRS / START_YEAR).", file=sys.stderr)
            sys.exit(1)

    csv_output_path = os.environ.get("CSV_OUTPUT_PATH", str(REPO_ROOT / "raw_weather" / "daily_weather.csv"))
    os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)

    print(f"Processing year dirs: {year_dirs}")
    print(f"CSV output: {csv_output_path}")

    df = weather_processing.build_daily_weather_dataframe_from_json(
        weather_years_dirs=year_dirs,
        output_path=csv_output_path,
    )
    print(f"\nWeather CHECKPOINT: {len(df)} daily rows built.")


if __name__ == "__main__":
    main()