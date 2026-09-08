import os
import calendar
from datetime import date
import pandas as pd # for making the DataFrames
from dateutil.relativedelta import relativedelta

# File Reading Helper Functions
def list_subdirectories(parent_dir: str) -> list[str]:
  """
  List all subdirectories of parent_dir that end in a 4-digit year (e.g., "labor_2023"),
  skipping unrelated folders such as Jupyter's ".ipynb_checkpoints".

  Args:
    parent_dir: string, path to the folder containing the year subdirectories

  Returns:
    list of strings, full paths to each matching subdirectory, sorted by name
  """
  with os.scandir(parent_dir) as entries:
    return sorted(entry.path for entry in entries if entry.is_dir() and entry.name[-4:].isdigit())


# DataFrame sanity checks helper functions.
def column_exists(df: pd.DataFrame, column_name: str) -> bool:
  """
 Helper function to confirm if a column exists in a given dataframe
  Args:
    df: Dataframe to inspect
    column_name: string of the column to look for in df

  Returns:
    Boolean confirmation of the column existinf in the dataframe
  """
  return column_name in df.columns


def confirm_columns_exist(df: pd.DataFrame, columns: list) -> bool:
   """
   Helper function to check if all requested columns exist.
   Args:
    df: DataFrame to be checked
    list: List of columns to be looked for inside the df

    Returns:
      Boolean confirming the presence or absence of the columns set into the df.
    """
   return set(columns).issubset(df.columns)


def reorder_dataframe(df: pd.DataFrame, column_order: list) -> pd.DataFrame:
  """
  Reorder DataFrame columns
  Args:
    df: DataFrame to be edited
  Returns:
    df: DataFrame with reordered columns
  """

  if confirm_columns_exist(df=df, columns=column_order):
    df = df[column_order]
    return df

  else:
    raise ValueError(f'the dataframe frovided does not have all the columns requested: {column_order}')


# JSON file sanity checks helper functions
def is_json_file(filepath: str) -> bool:
  """
  helper function to confirm a file is JSON
  Args:
    filepath: string of the file's path

  Returns:
    boolean confirmtion that the file is a JSON file.
  """
  return filepath.is_file() and filepath.name.lower().endswith(".json")


def month_chunks(start_date: date, end_date: date):
  """
  Splits [start_date, end_date] (inclusive) into per-calendar-month segments,
  each clipped to the requested range, so callers can keep making one API
  call per calendar month touched as in earlier designs.

  A whole-month request (day 1 through that month's last day) yields exactly one segment with is_full_month=True 
  use this to keep the existing "{year}_{month:02d}" filename and skip-if-exists caching unchanged for historical/backfill runs. 
  A partial range (e.g. "last 7 days" for a scheduled incremental run) yields a segment with is_full_month=False, naming that file after the exact days covered instead.

  Args:
    start_date: date, inclusive start of the overall range
    end_date: date, inclusive end of the overall range

  Returns:
    Yields (year, month, day_start, day_end, is_full_month) tuples, one per
    calendar month touched by [start_date, end_date].
  """
  current = start_date.replace(day=1)

  while current <= end_date:
    last_day = calendar.monthrange(current.year, current.month)[1]
    month_start = max(current, start_date)
    month_end = min(current.replace(day=last_day), end_date)
    is_full_month = (month_start.day == 1 and month_end.day == last_day)
    yield current.year, current.month, month_start.day, month_end.day, is_full_month
    current = current.replace(day=1) + relativedelta(months=1)