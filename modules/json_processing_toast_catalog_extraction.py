import json  # for reading the JSON files
import os
import pandas as pd # for making the DataFrames
#from datetime import datetime  # for parsing the ISO 8601 timestamp strings from Toast
#from pathlib import Path #for handling path
from typing import Optional
#from zoneinfo import ZoneInfo  # for the given timezone


##____________________________QUALITY CHECK CATALOGS___________________________________________________
def is_catalog_file(path: str, catalog_type: Optional[str] = None) -> bool:
    if not catalog_type:
        raise ValueError("No catalog type has been specified.")

    expected_suffix = f"catalog_{catalog_type}.json".lower()
    return os.path.isfile(path) and path.lower().endswith(expected_suffix)


def require_catalog_file(path: str, catalog_type: str) -> None:
    """Raise a descriptive ValueError if `path` isn't a valid catalog file of this type."""
    if not is_catalog_file(path, catalog_type):
        raise ValueError(f"Invalid catalog file: got {path!r}, expected a file named "
                         f"'catalog_{catalog_type}.json'.")


##____________________________build DataFrames from TOAST's CATALOGS___________________________________________________
# CATALOGS list all the GUIDS handles by toast, their use is mapping the JSON raw files' GUIDs
# with actual concepts.
def build_dataframe_from_json_dining_option(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns "dining_option_guid" and "dining_option" to map GUIDs

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, save Dataframe with columns "dining_option_guid" and "dining_option"
  """
  require_catalog_file(filepath, catalog_type="dining_options")
  with open(filepath, "r", encoding="utf-8") as f:
            options = json.load(f)
  rows = []

  for option in options:
    dining_option_guid = option.get("guid")
    name = option.get("name")
    row = {"dining_option_guid":dining_option_guid   ,"dining_option":name}
    rows.append(row)

  dining_options_df = pd.DataFrame(rows)

  dining_options_df.to_csv(output_file, index=False)


def build_dataframe_from_json_revenue_centers(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns "revenue_center_guid" and "revenue_center" to map GUIDs

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, save Dataframe with columns "revenue_center_guid" and "revenue_center"
  """
  require_catalog_file(filepath, catalog_type="revenue_centers")
  with open(filepath, "r", encoding="utf-8") as f:
          options = json.load(f)
  rows = []

  for option in options:
    revenue_center_guid   = option.get("guid")
    name = option.get("name")
    row = {"revenue_center_guid":revenue_center_guid, "revenue_center":name}
    rows.append(row)

  df = pd.DataFrame(rows)
  df.to_csv(output_file, index=False)


def build_dataframe_from_json_sales_category(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns "sales_category_guid" and "category" to map GUIDs

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, saves Dataframe with columns "sales_category_guid" and "category"
  """
  require_catalog_file(filepath, catalog_type="sales_categories")
  with open(filepath, "r", encoding="utf-8") as f:
          options = json.load(f)
  rows = []

  for option in options:
    sales_category_guid = option.get("guid")
    name = option.get("name")
    row = {"sales_category_guid":sales_category_guid, "category":name}
    rows.append(row)

  df = pd.DataFrame(rows)
  df.to_csv(output_file, index=False)


def build_dataframe_from_json_menu_items(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns "item_guid" and "item" to map GUIDs

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, saves Dataframe with columns "item_guid" and "item"
  """
  require_catalog_file(filepath, catalog_type="menu_items")
  with open(filepath, "r", encoding="utf-8") as f:
          options = json.load(f)
  rows = []

  for option in options:
    item_guid = option.get("guid")
    name = option.get("name")
    row = {"item_guid":item_guid, "item":name}
    rows.append(row)

  df = pd.DataFrame(rows)
  df.to_csv(output_file, index=False)


def build_dataframe_from_json_menu_groups(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns "item_group_guid" and "item group" to map GUIDs

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, save Dataframe with columns "item_group_guid" and "item group"
  """
  require_catalog_file(filepath, catalog_type="menu_groups")
  with open(filepath, "r", encoding="utf-8") as f:
          options = json.load(f)
  rows = []

  for option in options:
    item_group_guid = option.get("guid")
    name = option.get("name")
    row = {"item_group_guid":item_group_guid, "item group":name.lower()}
    rows.append(row)

  df = pd.DataFrame(rows)
  df.to_csv(output_file, index=False)


def build_dataframe_tables(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns "table_guid" and "table_number" to map GUIDs

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, save Dataframe with columns "table_guid" and "table_number"
  """
  require_catalog_file(filepath, catalog_type="tables")
  with open(filepath, "r", encoding="utf-8") as f:
          options = json.load(f)
  rows = []

  for option in options:
    # Context to Order Level
    sales_category_guid = option.get("guid")
    name = option.get("name")
    row = {"table_guid":sales_category_guid, "table_number": 'Table ' + name}
    rows.append(row)

  df = pd.DataFrame(rows)
  df.to_csv(output_file, index=False)


def build_dataframe_from_json_employees(filepath: str, output_file: str) -> pd.DataFrame:
  """
  Build a Dataframe with columns

  Args:
    filepath: string, to the catalog JSON file.

  Returns:
    None, save Dataframe with columns "employee_guid" and "employee_full_name"
  """
  require_catalog_file(filepath, catalog_type="employees")
  with open(filepath, "r", encoding="utf-8") as f:
          employees = json.load(f)
  rows = []
  for emp in employees:
    row = {"employee_guid": emp.get("guid"),
           "first_name": emp.get("firstName"),
            "last_name": emp.get("lastName"),
            # Concatenate first + last into a single display label for Power BI
            "employee_full_name": f"{emp.get('firstName', '')} {emp.get('lastName', '')}".strip(),
            "email": emp.get("email"),
            # Keep deleted employees for historical time entries
            "deleted": emp.get("deleted", False),
        }
    rows.append(row)
  df = pd.DataFrame(rows)
  df = df[['employee_guid', 'employee_full_name']]
  df.to_csv(output_file, index=False)


def build_dataframe_from_json_jobs(filepath: str, output_file: Optional[str] = None) -> pd.DataFrame:
  """
  Build a Dataframe with columns

  Args:
    filepath: string, to the catalog JSON file.
    output_file: optional string, path to save the CSV to. If omitted, the
      DataFrame is only returned in memory (e.g. for merging into another
      DataFrame) and no CSV is written.

  Returns:
    df: DataFrame with columns "job_guid", "title", "code", "default_wage", "tipped", "deleted".
    Also saves df to output_file as CSV if output_file is provided.
  """
  require_catalog_file(filepath, catalog_type="jobs")
  with open(filepath, "r", encoding="utf-8") as f:
          jobs = json.load(f)
  rows = []
  for job in jobs:
    row = { "job_guid": job.get("guid"),
            "title": job.get("title"),        # human-readable role name: "Server", "Cook"
            "code": job.get("code"),          # optional short code set in Toast back-office
            "default_wage": job.get("defaultWage"),  # fallback wage if not set per employee
            # tipped=True means this is a FOH tipped role (server, bartender).
            # Use this flag to split labor cost into FOH vs. BOH in Power BI.
            "tipped": job.get("tipped", False),
            "deleted": job.get("deleted", False),}
    rows.append(row)

  df = pd.DataFrame(rows)
  if output_file:
    df.to_csv(output_file, index=False)
  return df