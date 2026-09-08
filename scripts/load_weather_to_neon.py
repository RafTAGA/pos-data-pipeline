"""
scripts/load_weather_to_neon.py

Upserts the processed Open-Meteo weather CSV into its Neon table.
Reads the CSV written by scripts/process_weather_to_df.py.

Environment variables:
    WEATHER_OUTPUT_DIR      Folder containing daily_weather.csv.
                             Defaults to raw_weather (repo-root relative) --
                             matches process_weather_to_df.py's default.
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
from schemas import WEATHER_DAILY_SUMMARY  # type: ignore

WEATHER_MAP = {"weather_daily_summary": {"csv": "daily_weather.csv",
                                        "key_columns": ["yyyymmdd"],
                                        "schema": WEATHER_DAILY_SUMMARY,}}

def main() -> None:
    weather_dir = os.environ.get("WEATHER_OUTPUT_DIR", str(REPO_ROOT / "raw_weather"))
    engine = db_neon.get_neon_engine()

    for table_name, config in WEATHER_MAP.items():
        csv_path = os.path.join(weather_dir, config["csv"])
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

    print("\nCHECKPOINT: Weather Neon upsert complete.")

if __name__ == "__main__":
    main()
