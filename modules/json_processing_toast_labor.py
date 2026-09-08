#Labor Dataframe
import os
import pandas as pd
import general_data_processing as processing # type: ignore
import json  # for reading the JSON files
import json_processing_toast_catalog_extraction as catalog # type: ignore

### Refunds files
def extract_time_entry_rows_from_file(filepath:str) -> list[dict]:
    """
    Converts a list of raw TimeEntry dicts (as returned by Toast) into a flat list of rows.
    Args:
    filepath: string, to a JSON file of a 30 day labor period

    Returns:
      rows: list of dicts, one per TimeEntry, with the fields needed to total hours by day
      (and, if needed later, by employee or job).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        time_entries = json.load(f)
    rows = []
    for te in time_entries or []:
      # Both employeeReference and jobReference come as {"guid": "...", "entityType": "..."}
      # Use `or {}` to safely handle null references without crashing on .get()
      employee_ref = te.get("employeeReference") or {}
      job_ref      = te.get("jobReference")      or {}

      # Hours worked — Toast splits into regular (first 40 h/week) and overtime (beyond 40 h)
      regular_hours  = te.get("regularHours")  or 0
      overtime_hours = te.get("overtimeHours") or 0
      total_hours = regular_hours + overtime_hours

      # Wage fields — Toast populates these when the employee has a configured wage.
      # hourlyWage: the rate for this specific time entry (may differ from job default_wage
      #             if the employee has an individual override)
      # regularPay: regularHours × hourlyWage (computed by Toast)
      # overtimePay: overtimeHours × (1.5 × hourlyWage) (computed by Toast)
      # Left as None (not 0.0) when missing so complement_dataframe_labor can tell
      # "no wage on this entry" apart from "wage is actually zero" and fall back
      # to the job's default_wage instead of silently zeroing out pay.
      hourly_wage  = te.get("hourlyWage")
      regular_pay  = regular_hours * hourly_wage if hourly_wage is not None else None
      overtime_pay = overtime_hours * hourly_wage if hourly_wage is not None else None

      # businessDate: the restaurant's "which day does this shift count toward" field.
      # Accounts for the closeout hour (default 4 AM) so a shift ending at 1 AM
      # belongs to the PREVIOUS day's business date, not the calendar day it ended on.
      business_date = te.get("businessDate")
      if business_date is not None:
        business_date = str(business_date)

      rows.append({"time_entry_guid": te.get("guid"),
                   "employee_guid":   employee_ref.get("guid"),
                   "job_guid":        job_ref.get("guid"),
                   "business_date":   business_date,
                   "in_date":         te.get("inDate"),   # clock-in timestamp (UTC)
                   "out_date":        te.get("outDate"),  # clock-out timestamp (UTC)
                   "regular_hours":   regular_hours,
                   "overtime_hours":  overtime_hours,
                   "total_hours":     total_hours,
                   "hourly_wage":     hourly_wage,        # rate for this entry
                   "regular_pay":     regular_pay,        # regular labor cost for this entry
                   "overtime_pay":    overtime_pay,       # overtime labor cost for this entry
                   "total_pay":       total_hours * hourly_wage if hourly_wage is not None else None,  # full labor cost for this entry
                   "deleted":         te.get("deleted", False),    })
    return rows


def aggregate_daily_hours(df:pd.DataFrame) -> pd.DataFrame:
    """
    Totals hours AND pay by business_date across all time entries.
    Extended from the original to sum total_pay.

    Args:
        rows: list of flat row dicts from extract_time_entry_rows_from_file()

    Returns:
        df: DataFrame with one row per business_date including both hours and pay totals
    """
    columns = [
        "yyyyMMdd",
        "regular_hours", "overtime_hours", "total_hours", "total_pay",
        "entry_count", "employee_count",
    ]

    # Exclude deleted/archived entries — they represent corrections, not actual hours worked
    if df.empty:
      return pd.DataFrame(columns=columns)

    df = df[df["deleted"] != True]

    daily_df = (
        df.groupby("yyyyMMdd", as_index=False)
          .agg(
              regular_hours  = ("regular_hours",   "sum"),
              overtime_hours = ("overtime_hours",  "sum"),
              total_pay      = ("total_pay",       "sum"),
              entry_count    = ("time_entry_guid", "count"),
              employee_count = ("employee_guid",   "nunique"),
          )
    )
    daily_df["total_hours"] = daily_df["regular_hours"] + daily_df["overtime_hours"]
    return daily_df


def extract_time_entry_rows_from_folder(labor_dir:str)  -> list[dict]:
  """
  Build rows for all the labor reports found in a directory.
  Args:
    labor_dir: string, to folder containing all the JSON files of a 30 day labour period

  Returns:
    rows for all the files in the directory.
  """
  all_rows = []
  found_json = False

  with os.scandir(labor_dir) as entries:
    for entry in entries:
      if processing.is_json_file(filepath=entry):
        found_json = True
        rows = extract_time_entry_rows_from_file(filepath=entry.path)
        all_rows += rows

  if not found_json:
    print("No JSON files found!!!!!")

  return all_rows


def extract_time_entry_rows_from_folders(labor_dirs:list[str])  -> list[dict]:
  """
  Build rows for all the labor reports found across multiple directories
  (e.g., one folder per year of exports). Reuses extract_time_entry_rows_from_folder
  per directory rather than building a DataFrame per folder, so the catalog merges
  and date math downstream only run once, on the combined rows.

  Args:
    labor_dirs: list of strings, each a folder containing JSON files of a labour period

  Returns:
    rows for all the files across all the directories.
  """
  all_rows = []
  for labor_dir in labor_dirs:
    all_rows += extract_time_entry_rows_from_folder(labor_dir=labor_dir)
  return all_rows


# def save_labor_watermark(df: pd.DataFrame, output_path: str) -> None:
#   """
#   Persist the earliest and latest business date found in df, so a future
#   incremental run knows what date range has already been ingested.

#   Args:
#     df: DataFrame produced by build_labor_dataframes (must already have the
#         "yyyyMMdd" datetime column added by complement_dataframe_with_dates)
#     watermark_path: string, path to the JSON file to write

#   Returns:
#     None. Writes {"first_date": ..., "last_date": ...} to output_path.
#   """
#   if not processing.column_exists(df, "yyyyMMdd"):
#     raise ValueError("Dataframe provided lacks a date column 'yyyyMMdd'.")

#   watermark = {
#       "first_date": df["yyyyMMdd"].min().strftime("%Y-%m-%d"),
#       "last_date":  df["yyyyMMdd"].max().strftime("%Y-%m-%d"),
#   }
#   with open(output_path, "w", encoding="utf-8") as f:
#     json.dump(watermark, f, indent=2)


def complement_dataframe_with_dates(labor_df:pd.DataFrame) -> pd.DataFrame:
  """
  Make extra columns for KPI calculation
  Args:
    df: DataFrame, to be edited
  Returns:
    df: DataFrame with added columns
  """
  if processing.column_exists(labor_df, "yyyyMMdd"):
    labor_df["yyyyMMdd"] = pd.to_datetime(labor_df["yyyyMMdd"].astype(str), format="%Y%m%d", errors="coerce")
    # labor_df["year"] = labor_df["yyyyMMdd"].dt.to_period('Y')
    # labor_df['year_month'] = labor_df["yyyyMMdd"].dt.to_period('M')
    # labor_df['year_week'] = labor_df["yyyyMMdd"].dt.to_period('W')
    return labor_df
  else:
    raise ValueError(f"Dataframe provided lacks a date column 'yyyyMMdd'.")


def complement_dataframe_labor (labor_df:pd.DataFrame, #employee_filepath: str, 
                                jobs_filepath:str) -> pd.DataFrame:
  
  #employees_df = catalog.build_dataframe_from_json_employees(employee_filepath)
  jobs_df = catalog.build_dataframe_from_json_jobs(jobs_filepath)

  # df = labor_df.merge(employees_df[['employee_guid', 'employee_full_name']],
  #             left_on='employee_guid',
  #             right_on='employee_guid', how='left')
  # df.drop(columns=['employee_guid'], inplace=True)


  df = labor_df.merge(jobs_df[['job_guid', 'title', 'default_wage']],
                left_on='job_guid',
                right_on='job_guid', how='left')
  df.drop(columns=['job_guid'], inplace=True)

  # Fall back to the job's default wage when a time entry has no wage of its own,
  # then recompute pay for just those rows. Anything still missing (no job match
  # either) settles to 0 so downstream sums don't break on NaN.
  missing_wage = df['hourly_wage'].isna()
  df.loc[missing_wage, 'hourly_wage'] = df.loc[missing_wage, 'default_wage']
  df.loc[missing_wage, 'regular_pay'] = df.loc[missing_wage, 'regular_hours'] * df.loc[missing_wage, 'hourly_wage']
  df.loc[missing_wage, 'overtime_pay'] = df.loc[missing_wage, 'overtime_hours'] * df.loc[missing_wage, 'hourly_wage']
  df.loc[missing_wage, 'total_pay'] = df.loc[missing_wage, 'total_hours'] * df.loc[missing_wage, 'hourly_wage']
  df.drop(columns=['default_wage'], inplace=True)

  # If a time entry still has no wage after the fallback, it means the job itself
  # had no default_wage set (or job_guid didn't match any job) — these entries are
  # about to be zero-filled below, which would otherwise understate labor cost silently.
  still_missing = df['hourly_wage'].isna()
  if still_missing.any():
    print(f"WARNING: {still_missing.sum()} time entries have no wage and no job "
          f"default_wage to fall back on; their pay is being set to 0. "
          f"Affected time_entry_guids: {df.loc[still_missing, 'time_entry_guid'].tolist()}")

  df[['hourly_wage', 'regular_pay', 'overtime_pay', 'total_pay']] = (
      df[['hourly_wage', 'regular_pay', 'overtime_pay', 'total_pay']].fillna(0.0)
  )
  return df


def build_labor_dataframes(years_labor_dirs:list[str], 
                           output_dir:str, #employee_filepath: str, 
                           jobs_filepath:str, #  watermar_path: str = None
                           ) -> pd.DataFrame:
  """
  Args:
    labor_dirs: string (single folder) or list of strings (e.g., one folder per year),
      each containing the 30-day-period JSON exports to process.
    output_dir: string, path to write the combined labor CSV to.
    employee_filepath: string, path to the employees catalog JSON file.
    jobs_filepath: string, path to the jobs catalog JSON file.
    watermark_path: optional string, path to a JSON file recording the earliest/latest
      business date processed. Pass this so a future incremental run knows where to
      resume from; omit it to skip watermark tracking.

  Returns:
    df: combined labor DataFrame across all labor_dirs.
  """
  #catalog.require_catalog_file(employee_filepath, catalog_type="employees")
  catalog.require_catalog_file(jobs_filepath, catalog_type="jobs")

  if isinstance(years_labor_dirs, str):
    years_labor_dirs = [years_labor_dirs]

  all_rows = extract_time_entry_rows_from_folders(labor_dirs=years_labor_dirs)
  df = pd.DataFrame(all_rows, columns=["time_entry_guid", "employee_guid", "job_guid", "business_date",
                                       "in_date", "out_date", "regular_hours", "overtime_hours",
                                       "total_hours", "hourly_wage", "regular_pay", "overtime_pay",
                                       "total_pay", "deleted"])

  if "business_date" in df.columns:
    df["yyyyMMdd"] = df["business_date"]
    df.drop(columns=["business_date"], inplace=True)

  # Toast's businessDate can extend past local midnight, so an order right at a
    # month boundary (e.g. late on Dec 31) can be returned by both the outgoing and
    # incoming month's API query window in run_order_extraction, producing exact
    # duplicate check/item rows once two monthly JSON files are combined here.
    before_labor = len(df)
    df = df.drop_duplicates(subset=["time_entry_guid"], keep="first")
    if len(df) != before_labor:
      print(f"Dropped {before_labor - len(df)} duplicate check_guid row(s) (month-boundary overlap).")
  

  df = complement_dataframe_with_dates(labor_df=df)
  df = complement_dataframe_labor(labor_df=df, #employee_filepath, 
                                  jobs_filepath=jobs_filepath)
  # df_hours = aggregate_daily_hours(df)
  df.to_csv(output_dir, index=False)

  # if watermar_path:
  #   save_labor_watermark(df, watermar_path)

  return df


