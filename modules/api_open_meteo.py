import requests # type: ignore
import json
import time
import os
from datetime import date
from typing import Literal
import general_data_processing as processing # type: ignore


DEFAULT_LAT = 29.76
DEFAULT_LON = -95.36
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SLEEP_BETWEEN_MONTHS = 1.0  # secs between monthly requests
MAX_RETRIES_PER_REQUEST = 3
# Daily variables, full list: https://open-meteo.com/en/docs/historical-weather-api
DAILY_VARIABLES = ["temperature_2m_max", 
                   "temperature_2m_min", 
                   "temperature_2m_mean", 
                   "apparent_temperature_max", 
                   "apparent_temperature_min", 
                   "precipitation_sum", 
                   "rain_sum", 
                   "precipitation_hours",
                   "snowfall_sum", # rare in Houston, but a near-zero-sales flag when it hits (e.g. Uri 2021, Jan 2024/2025)
                   "windspeed_10m_max", 
                   "windgusts_10m_max", 
                   "relative_humidity_2m_mean", 
                   "cloudcover_mean", 
                   "shortwave_radiation_sum",   # total solar energy (MJ/m^2) — "how sunny," not "how hot"; proxy for patio/outdoor traffic
                   ]

def metrics_to_use(metrics: Literal["US", "INT"] = "US") -> tuple[str, str, str]:
    """
    Defines the meassure units for the data to extrcat
    Args:
        metrics: str between US and INT, default being US

    Returns:
        TEMPERATURE_UNIT: str "farenheit" or "celsius"
        WINDSPEED_UNIT: str "mph" or "kmh"
        PRECIPITATION_UNIT: str "inch" or "mm"

    """
    if metrics=='US':
        TEMPERATURE_UNIT = "fahrenheit"
        WINDSPEED_UNIT = "mph"
        PRECIPITATION_UNIT = "inch"

    elif metrics=='INT':
        TEMPERATURE_UNIT = "celsius"
        WINDSPEED_UNIT = "kmh"
        PRECIPITATION_UNIT = "mm"

    else:
        raise ValueError("Specify a Metric for the Variables to collect: ['US' or 'INT']")

    return TEMPERATURE_UNIT, WINDSPEED_UNIT, PRECIPITATION_UNIT


TEMPERATURE_UNIT, WINDSPEED_UNIT, PRECIPITATION_UNIT = metrics_to_use()


##____________________________API WEATHER EXTRACTION FUNCTIONS___________________________________________________
def fetch_weather_range(start_date_str: str, end_date_str: str,
                        latitude: float = DEFAULT_LAT, longitude: float = DEFAULT_LON) -> None:
    """
    Calls the Open-Meteo Historical Weather (archive) API for a date range.
    Full start/end range in a single call (no pagination, no auth token).
    Returns one array per variable, aligned
    by index to the "time" array.
    Args:
      start_date_str: "YYYY-MM-DD", inclusive
      end_date_str: "YYYY-MM-DD", inclusive
      latitude: restaurant's location latitude (defaults to Houston, TX)
      longitude: restaurant's location longitude (defaults to Houston, TX)

    Returns:
      Dict of the raw JSON response ("daily" key holds the parallel arrays),
      or None if the request failed after retries.
    """
    params = {
              "latitude": latitude,
              "longitude": longitude,
              "start_date": start_date_str,
              "end_date": end_date_str,
              "daily": ",".join(DAILY_VARIABLES),
              "temperature_unit": TEMPERATURE_UNIT,
              "windspeed_unit": WINDSPEED_UNIT,
              "precipitation_unit": PRECIPITATION_UNIT,
              "timezone": "America/Chicago",  # Houston's IANA timezone (handles CST/CDT)
             }

    retry_count = 0
    while retry_count < MAX_RETRIES_PER_REQUEST:
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params)

        if response.status_code == 429:
            print(f"  Rate limited fetching {start_date_str}–{end_date_str}. Waiting 15 seconds...")
            time.sleep(15)
            continue  # retry without incrementing retry_count

        if response.status_code == 200:
            return response.json()

        retry_count += 1
        print(f"  ERROR {response.status_code} fetching {start_date_str}–{end_date_str} "
              f"(attempt {retry_count}/{MAX_RETRIES_PER_REQUEST}).")
        print(f"  URL: {response.url}")
        print(f"  Server response: {response.text}")

        if response.status_code >= 500 and retry_count < MAX_RETRIES_PER_REQUEST:
            wait = 5 * retry_count
            print(f"  Retrying in {wait} seconds...")
            time.sleep(wait)
        else:
            break  # 4xx (bad params, etc.): no point retrying

    print(f"  FAILED to fetch weather for {start_date_str}–{end_date_str}.")
    return None


def flatten_daily_weather(raw_response: dict) -> list[dict]:
    """
    Flattens Open-Meteo's parallel-array "daily" block into one flat row per
    date — same flat-table-first convention used for Toast orders/labor,
    so this can go straight into a df_clean-style DataFrame without re-fetching.
    Args:
      raw_response: dict, the raw JSON returned by fetch_weather_range()

    Returns:
      List of row dicts, one per date, e.g.:
      [{"date": "2025-01-01", "temperature_2m_max": 61.2, ...}, ...]
      Returns an empty list if raw_response is None or has no "daily" block.
    """
    if not raw_response or "daily" not in raw_response:
        return []

    daily = raw_response["daily"]
    dates = daily.get("time", [])
    rows = []

    for idx, date_str in enumerate(dates):
        row = {"date": date_str}
        for var in DAILY_VARIABLES:
            values = daily.get(var, [])
            row[var] = values[idx] if idx < len(values) else None
        rows.append(row)

    return rows


def run_weather_extraction(start_date: tuple, end_date: tuple,
                           output_dir: str, latitude: float = DEFAULT_LAT,
                           longitude: float = DEFAULT_LON) -> None:
    """
    Extracts historical daily weather between start_date and end_date, one
    calendar-month segment at a time (clipped to the exact days requested),
    saving both the raw API response and a flattened row-per-day version for
    each segment. Mirrors run_order_extraction's structure (skip-if-exists,
    per-segment save, error handling).
    Args:
      start_date: tuple (year, month, day), inclusive start
      end_date: tuple (year, month, day), inclusive end
      output_dir: directory to save JSON files into
      latitude: restaurant's location latitude (defaults to Houston, TX)
      longitude: restaurant's location longitude (defaults to Houston, TX)

    Returns:
      None. Saves one raw JSON file and one flattened JSON file per segment.
    """
    os.makedirs(output_dir, exist_ok=True)

    for year, month, day_start, day_end, is_full_month in processing.month_chunks(date(*start_date), date(*end_date)):
        label = f"{year}_{month:02d}" if is_full_month else f"{year}_{month:02d}_{day_start:02d}to{day_end:02d}"
        raw_output_path = os.path.join(output_dir, f"weather_raw_{label}.json")
        flat_output_path = os.path.join(output_dir, f"weather_flat_{label}.json")

        if os.path.exists(flat_output_path):
            print(f"[{label}] Already extracted, skipping.")
            continue

        start_str = date(year, month, day_start).strftime("%Y-%m-%d")
        end_str = date(year, month, day_end).strftime("%Y-%m-%d")

        print(f"\nExtracting weather for [{label}] ({start_str} to {end_str})...")

        try:
            raw_response = fetch_weather_range(start_date_str=start_str, end_date_str=end_str, latitude=latitude, longitude=longitude)

        except requests.exceptions.RequestException as e:
            print(f"[{label}] ERROR: {e}")
            print("Stopping extraction due to ERROR. Please review the ERROR.")
            break

        if raw_response is None:
            print(f"[{label}] WARNING: no data returned, skipping save for this range.")
            time.sleep(SLEEP_BETWEEN_MONTHS)
            continue

        flat_rows = flatten_daily_weather(raw_response)

        # Save raw JSON (audit trail, same convention as Toast raw JSON saves)
        with open(raw_output_path, "w", encoding="utf-8") as f:
            json.dump(raw_response, f, ensure_ascii=False, indent=2)

        # Save flattened rows (ready to load straight into pandas)
        with open(flat_output_path, "w", encoding="utf-8") as f:
            json.dump(flat_rows, f, ensure_ascii=False, indent=2)

        print(f"[{label}] Saved: {len(flat_rows)} daily rows to: {flat_output_path}")
        time.sleep(SLEEP_BETWEEN_MONTHS)

    print("\nWEATHER EXTRACTION COMPLETE or STOPPED BY ERROR, CONFIRM WITH LOGS!")


