import json
import pandas as pd
import os
import general_data_processing as processing


def parse_weather_data_year(weather_year_dir: str) -> tuple[list[dict], int]:
    """
    Reads all Open-Meteo monthly flattened JSON files within a year folder into
    a list of dicts, one per day of weather data.

    Args:
        weather_year_dir: string, path to the folder containing all monthly
                           weather_flat_*.json files for a year

    Returns:
        year_rows: list of dicts, each one a DataFrame row
        files_processed: int, count of monthly files read
    """
    year_rows = []
    files_processed = 0
    with os.scandir(weather_year_dir) as months:
        for month in months:
            if processing.is_json_file(month) and month.name.startswith("weather_flat_"):
                with open(month, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                year_rows += rows
                files_processed += 1
    if files_processed == 0:
        raise ValueError(f"No JSON files found in {weather_year_dir}")

    print(f"Total rows: {len(year_rows)}")
    return year_rows, files_processed


def parse_weather_data_years(weather_years_dirs: list[str]) -> list[dict]:
    """
    Reads all Open-Meteo monthly flattened JSON files across multiple year
    folders into a single list of dicts, one per day of weather data.

    Args:
        weather_years_dirs: list of strings, each a folder containing a year's
                             worth of monthly weather_flat_*.json files

    Returns:
        List of dicts, each one a DataFrame row, combined across all years.
    """
    all_rows = []
    total_files_processed = 0
    for weather_year_dir in weather_years_dirs:
        year_rows, year_files_processed = parse_weather_data_year(weather_year_dir)
        print(f"Files processed for directory {weather_year_dir}:")
        print(f"\t{year_files_processed}")
        all_rows += year_rows
        total_files_processed += year_files_processed

    print(f"Total files processed across all folders: {total_files_processed}")
    return all_rows


def complement_dataframe_with_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes Open-Meteo's "date" column (returned as "YYYY-MM-DD") into the
    same yyyyMMdd convention used across the Toast and MarginEdge pipelines, so
    weather can be joined onto daily sales/labor without a format-conversion
    step downstream in Power BI or SQL.

    Args:
      df: DataFrame with a "date" column in "YYYY-MM-DD" string format

    Returns:
      df with yyyyMMdd (datetime), year, year_month, year_week columns added,
      matching complement_dataframe_with_dates in the other json_processing modules.
    """
    if not processing.column_exists(df, "date"):
        raise ValueError("Dataframe provided lacks a date column 'date'.")

    df["yyyyMMdd"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    # df["year"] = df["yyyyMMdd"].dt.to_period("Y")
    # df["year_month"] = df["yyyyMMdd"].dt.to_period("M")
    # df["year_week"] = df["yyyyMMdd"].dt.to_period("W")
    df = df.drop(columns=["date"])
    return df


def build_daily_weather_dataframe_from_json(weather_years_dirs, output_path: str) -> pd.DataFrame:
    """
    Builds a daily weather DataFrame from the flattened JSON files saved by
    run_weather_extraction, date-standardized to yyyyMMdd for downstream joins.

    Args:
        weather_years_dirs: string (single folder) or list of strings (one
                             folder per year), each containing monthly
                             weather_flat_*.json files.
        output_path: string, path to write the resulting CSV to.

    Returns:
        Daily weather DataFrame, one row per date.
    """
    if isinstance(weather_years_dirs, str):
        weather_years_dirs = [weather_years_dirs]

    rows = parse_weather_data_years(weather_years_dirs=weather_years_dirs)
    if not rows:
        df = pd.DataFrame(columns=["date", "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                                    "apparent_temperature_max", "apparent_temperature_min", "precipitation_sum",
                                    "rain_sum", "precipitation_hours", "snowfall_sum", "windspeed_10m_max",
                                    "windgusts_10m_max", "relative_humidity_2m_mean", "cloudcover_mean",
                                    "shortwave_radiation_sum"])
    else:
        df = pd.DataFrame(rows)
    df = complement_dataframe_with_dates(df)
    df.to_csv(output_path, index=False)
    return df