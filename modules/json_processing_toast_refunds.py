import json  # for reading the JSON files
import os #for path handling
import pandas as pd # for making the DataFrames
import general_data_processing as processing # type: ignore
#from datetime import datetime  # for parsing the ISO 8601 timestamp strings from Toast
#from pathlib import Path #for handling path
#from zoneinfo import ZoneInfo  # for the given timezone

def parse_refunds_json_summary(filepath: str) -> list[dict]:
    """
    Reads a monthly refunds JSON file (from run_refund_extraction) into a daily
    summary: total sales refunded and total tips refunded per business date.
    Per Toast's net sales guidance: subtract refund.refundAmount from net sales,
    but NOT tip_refund_amount, since tips were never part of net sales.
    Args:
        filepath: path to the monthly refunds JSON file.

    Returns:
        List of dicts: {yyyyMMdd, refund_amount, tip_refund_amount}
    """
    with open(filepath, "r", encoding="utf-8") as f:
        payments = json.load(f)

    rows = []
    
    for payment in payments:
      guid = payment.get("guid")
      refund = payment.get("refund")
      if not refund:
        continue
      rows.append({"guid": guid, 
                   "yyyyMMdd": refund.get("refundBusinessDate"),
                   "refund_amount": refund.get("refundAmount", 0.0),
                   "tip_refund_amount": refund.get("tipRefundAmount", 0.0),
                   })

    return rows


def parse_refunds_summary_year(refunds_dir: str) -> list[dict]:
  """
  Build rows for all the refund reports found in a directory.
  Args:
    refunds_dir: string, to folder containing all the JSON files of a monthly refunds period

  Returns:
    rows for all the files in the directory.
  """
  all_rows = []
  found_json = False

  with os.scandir(refunds_dir) as months:
    for month in months:
      if processing.is_json_file(month):
        found_json = True
        rows = parse_refunds_json_summary(month.path)
        all_rows += rows

  if not found_json:
    print("No JSON files found!!!!!")

  return all_rows


def parse_refunds_summary_years(refunds_years_dirs: list[str]) -> list[dict]:
  """
  Build rows for all the refund reports found across multiple directories
  (e.g., one folder per year of exports). Reuses extract_refund_daily_rows_from_folder
  per directory rather than building a DataFrame per folder, so the aggregation
  downstream only runs once, on the combined rows.
  Args:
    refunds_dirs: list of strings, each a folder containing JSON files of a refunds period

  Returns:
    rows for all the files across all the directories.
  """
  all_rows = []
  for refund_year_dir in refunds_years_dirs:
    all_rows += parse_refunds_summary_year(refund_year_dir)
  return all_rows


def build_refunds_dataframe_from_rows(rows: list[dict]) -> pd.DataFrame:
  """
  Builds a daily refunds summary DataFrame from flat refund rows.
  Args:
    rows: list of dicts, one per refund, as returned by extract_refund_daily_rows_from_folder(s)

  Returns:
    Dataframe with columns "yyyyMMdd", "refund_amount", "tip_refund_amount" — one row per business date.
  """
  if not rows:
    empty = pd.DataFrame(columns=["guid", "yyyyMMdd", "refund_amount", "tip_refund_amount"])
    empty["yyyyMMdd"] = pd.to_datetime(empty["yyyyMMdd"])
    return empty

  df = pd.DataFrame(rows)
  df["yyyyMMdd"] = pd.to_datetime(df["yyyyMMdd"].astype(str), format="%Y%m%d", errors="coerce")
  #df = df.groupby("yyyyMMdd").agg(refund_amount=("refund_amount", "sum"), tip_refund_amount=("tip_refund_amount", "sum"),).reset_index()
  return df


def build_refunds_dataframe(refunds_years_dirs: list[str], output_dir: str) -> pd.DataFrame:
  """
  Builds a daily refunds summary DataFrame across all monthly refund JSON files
  found in refunds_dir: total refund amount and tip refund amount per business date.
  Args:
    refunds_dir: string (single folder) or list of strings (e.g., one folder per year),
      each containing monthly refund JSON files.
    output_dir: string, path to write the combined refunds CSV to.

  Returns:
    Dataframe with columns "yyyyMMdd", "refund_amount", "tip_refund_amount"
  """
  # if isinstance(refunds_dir, str):
  #   refunds_dir = [refunds_dir]
  rows = parse_refunds_summary_years(refunds_years_dirs)
  df = build_refunds_dataframe_from_rows(rows)
  df.to_csv(output_dir, index=False)
  return df