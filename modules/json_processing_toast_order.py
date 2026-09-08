import json  # for reading the JSON files
import os #for path handling
import pandas as pd # for making the DataFrames
import general_data_processing as processing # type: ignore
import sys
from datetime import datetime  # for parsing the ISO 8601 timestamp strings from Toast
from pathlib import Path #for handling path
from zoneinfo import ZoneInfo  # for the given timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "module"
sys.path.insert(0, str(MODULE_DIR))
import general_data_processing as general

RESTAURANT_TIMEZONE = "America/Chicago"  # Central Time (CST/CDT), matches _parse_orders_hourly_json_sales
LOCAL_TZ = ZoneInfo(RESTAURANT_TIMEZONE)

def coerce_numeric_columns(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Force the given columns to numeric dtype, converting any unparseable
    value (blank string, None, stray text) to NaN instead of leaving the
    column as dtype object, which is what upstream tools like Neon read as text.
    Args:
      df: DataFrame, to be edited
      columns: column names to coerce

    Returns:
      df: DataFrame with the given columns coerced to numeric
    """
    for col in columns:
       if col in df.columns:
          df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def safe_get_guid(field: str) -> str:
    """
    Extract GUID from the JSON dictionary, return None if field is None.
    Args:
      field: JSON field of intrerest.

    Retruns:
      string or None if field is None
    """
    if field is None:
        return None

    return field.get("guid")

# ____________________________________PROCESS THE ORDER BULK JSON FROM TOAST__________________________

# def parse_orders_json(filepath: str) -> list[dict]:
#     """
#     Reads Toast's orders monthly JSON file into a list of dictionaries, one per item/selection sold.
#     Includes voided/deleted orders, checks, and items rather than filtering them out — each is tagged
#     with its own boolean flag (order_voided, check_voided, item_voided, order_deleted, check_deleted,
#     order_excess_food, is_paid) so downstream reports can filter or audit them explicitly.
#     Args:
#         filepath: string, path to the monthly JSON file

#     Returns:
#         List of dictionaries, each one being a DataFrame row.
#     """
#     with open(filepath, "r", encoding="utf-8") as f:
#         orders = json.load(f)

#     rows = []

#     for order in orders:
#         # Context to Order Level
#         order_guid = order.get("guid")
#         business_date = order.get("businessDate")  # ej. 20250115 (int)
#         source = order.get("source")
#         order_voided = bool(order.get("voided"))
#         order_deleted = bool(order.get("deleted"))
#         order_excess_food = bool(order.get("excessFood", False))
#         #opened_date = order.get("openedDate")
#         #closed_date = order.get("closedDate")
#         duration = order.get("duration")
#         #number_of_guests = order.get("numberOfGuests")
#         paid_date_str = order.get("paidDate")
#         is_paid = bool(paid_date_str)

#         # All fields below have their own dictionary, so extract the GUID from them:
#         #e.g,: "server": {"guid": "00000000-0000-0000-0000-000000000001", "entityType": "RestaurantUser", "externalId": null
#         #e.g.: "table": {"guid": "00000000-0000-0000-0000-000000000002", "entityType": "Table", "externalId": null}
#         #e.g.: "revenueCenter": {"guid": "00000000-0000-0000-0000-000000000003", "entityType": "RevenueCenter", "externalId": null}
#         #e.g.: "diningOption": {"guid": "00000000-0000-0000-0000-000000000004", "entityType": "DiningOption", "externalId": null}
#         server_guid = safe_get_guid(order.get("server"))
#         table_guid = safe_get_guid(order.get("table"))
#         revenue_center_guid = safe_get_guid(order.get("revenueCenter"))
#         dining_option_guid = safe_get_guid(order.get("diningOption"))


#         for check in order.get("checks", []):
#             check_guid = check.get("guid")
#             check_voided = bool(check.get("voided"))
#             check_deleted = bool(check.get("deleted"))
#             #check_total_amount = check.get("totalAmount")
#             #check_tax_amount = check.get("taxAmount")
#             #check_payment_status = check.get("paymentStatus")

#             #Content to Selection Level
#             for item in check.get("selections", []):
#                 item_voided = bool(item.get("voided"))
#                 row = {
#                       ## Order Identifiers
#                       "order_guid": order_guid,
#                       "order_voided": order_voided, 
#                       "order_deleted": order_deleted, 
#                       "is_paid": is_paid,
#                       "order_excess_food": order_excess_food,

#                       ## Check Identifiers
#                       "check_guid": check_guid, 
#                       "check_voided": check_voided, 
#                       "check_deleted": check_deleted,
#                       #"check_payment_status": check_payment_status,
#                       #"check_total_amount": check_total_amount,
#                       #"check_tax_amount": check_tax_amount,
#                       #"employee_guid": server_guid,

#                       ## Order Time Identifiers
#                       "yyyyMMdd": business_date,
#                       #"opened_date": opened_date,
#                       #"closed_date": closed_date,
#                       "sitting_duration_secs": duration,

#                       ## Restaurant Location Data
#                       "dining_option_guid": dining_option_guid,
#                       "revenue_center_guid": revenue_center_guid,
#                       #"source": source,
#                       "table_guid": table_guid,
#                       #"number_of_guests": number_of_guests,
#                       #"seat_number": item.get("seatNumber"),

                      
#                       ## Sold Item Data
#                       "selection_guid": item.get("guid"),
#                       "item_display_name": (item.get("displayName") or "").lower(),
#                       "item_guid": safe_get_guid(item.get("item")),
#                       "sales_category_guid": safe_get_guid(item.get("salesCategory")),
#                       "item_group_guid": safe_get_guid(item.get("itemGroup")),
#                       "item_voided": item_voided,

#                         ## Prices and Amounts
#                       "quantity": item.get("quantity"),
#                       "price": item.get("price"),
#                       "pre_discount_price": item.get("preDiscountPrice"),
#                       #"tax": item.get("tax"),
#                 }
#                 rows.append(row)
#     return rows


def parse_orders_json(filepath: str) -> list[dict]:
    """
    Reads Toast's orders monthly JSON file into a list of dictionaries, one per item/selection sold.
    Includes voided/deleted orders and checks (each tagged with its own boolean flag:
    order_voided, check_voided, item_voided, order_deleted, order_excess_food) so downstream
    reports can filter or audit them explicitly.

    UNPAID orders (no paidDate) are excluded entirely at parse time, since an order with
    no paidDate has no reliable "hour" to assign and represents an open/test-mode/interrupted
    order rather than a completed sale.

    Adds fields not present in the prior version, needed for the daily_sales and
    hourly_sales SQL views to be built directly on this item-level table:
      - "hour": local (America/Chicago) hour the order was OPENED (seated), derived
        from openedDate. Same value repeated on every item row belonging to that
        order (hour is an order-level fact, Toast does not provide it per item).
      - "paid_hour": local (America/Chicago) hour the order was PAID, derived from
        paidDate. This is the timestamp that should back an hourly *sales* report
        (openedDate is when the table was seated, always earlier than the sale).
      - "check_net_amount": check.amount minus any FUNDRAISING_CAMPAIGN service charge —
        the validated net-sales formula. Same value repeated on every item row belonging
        to that check. Downstream SQL views must DISTINCT on check_guid before summing
        this column, since it repeats once per item.
      - "number_of_guests": order-level guest count. Same value repeated on every check
        row belonging to that order — downstream SQL views must DISTINCT on order_guid
        before summing this column, since it repeats once per check.

    Excludes:
      - "selection_guid"
      - "item_display_name"
      - "item_guid"
      - "sales_category_guid"
      - "item_group_guid"
      - "item_voided"
      - "quantity"
      - "price"
      - "pre_discount_price"
      - As these will be in their own dataset
    
    Args:
        filepath: string, path to the monthly JSON file

    Returns:
        List of dictionaries, each one being a DataFrame row.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        orders = json.load(f)

    order_check_rows = []
    item_rows = []

    for order in orders:
        # Exclude unpaid orders entirely — no paidDate means no hour can be derived,
        # and these are open/test-mode/interrupted orders, not completed sales.
        paid_date_str = order.get("paidDate")
        if not paid_date_str:
            continue

        # Context to Order Level
        order_guid = order.get("guid")
        business_date = order.get("businessDate")  # ej. 20250115 (int)
        source = order.get("source")
        order_voided = bool(order.get("voided"))
        order_deleted = bool(order.get("deleted"))
        order_excess_food = bool(order.get("excessFood", False))
        duration = order.get("duration")
        number_of_guests = order.get("numberOfGuests", 0)
        opened_date_str = order.get("openedDate")
        hour = datetime.strptime(opened_date_str, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(LOCAL_TZ).hour
        paid_hour = datetime.strptime(paid_date_str, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(LOCAL_TZ).hour
        revenue_center_guid = safe_get_guid(order.get("revenueCenter"))
        dining_option_guid = safe_get_guid(order.get("diningOption"))
        table_guid = safe_get_guid(order.get("table"))

        for check in order.get("checks", []):
            check_guid = check.get("guid")
            check_voided = bool(check.get("voided"))
            check_deleted = bool(check.get("deleted"))
            check_net_amount = check.get("amount", 0.0)

            for service_charge in check.get("appliedServiceCharges", []) or []:
                if service_charge.get("serviceChargeCategory") == "FUNDRAISING_CAMPAIGN":
                    check_net_amount -= service_charge.get("chargeAmount", 0.0) or 0.0

            order_check_rows.append({
                                      "order_guid": order_guid,
                                      "order_voided": order_voided,
                                      "order_deleted": order_deleted,
                                      "order_excess_food": order_excess_food,
                                      "number_of_guests": number_of_guests,
                                      "check_guid": check_guid,
                                      "check_voided": check_voided,
                                      "check_deleted": check_deleted,
                                      "check_net_amount": check_net_amount,
                                      "yyyyMMdd": business_date,
                                      "hour": hour,
                                      "paid_hour": paid_hour,
                                      "sitting_duration_secs": duration,
                                      "dining_option_guid": dining_option_guid,
                                      "revenue_center_guid": revenue_center_guid,
                                      "table_guid": table_guid,
                                    })


            for item in check.get("selections", []):
                item_voided = bool(item.get("voided"))
                item_rows.append({
                                  "check_guid": check_guid,

                                  ## Sold Item Data
                                  "selection_guid": item.get("guid"),
                                  "item_display_name": (item.get("displayName") or "").lower(),
                                  "item_guid": safe_get_guid(item.get("item")),
                                  "sales_category_guid": safe_get_guid(item.get("salesCategory")),
                                  #"item_group_guid": safe_get_guid(item.get("itemGroup")),
                                  "item_voided": item_voided,

                                  ## Prices and Amounts
                                  "quantity": item.get("quantity"),
                                  "price": item.get("price"),
                                  "pre_discount_price": item.get("preDiscountPrice"),
                                  })
    return order_check_rows, item_rows


##__________________LOOP THROUGH A FOLDER WITH JSONS________________________________
def parse_orders_json_year(year_orders_dir:str):
  """
  Reads Toast's orders monthly JSON file from multiple year folders into a list of dictionaries, one per item/selection sold.
  Includes voided/deleted orders, checks, and items rather than filtering them out — each is tagged
  with its own boolean flag (order_voided, check_voided, item_voided, order_deleted, check_deleted,
  order_excess_food, is_paid) so downstream reports can filter or audit them explicitly.
  Args:
      orders_dir: string, path to the folder containing all JSON files file

  Returns:
      List of dictionaries, each one being a DataFrame row.
  """
  year_order_check_rows = []
  year_item_rows = []


  files_processed = 0
  with os.scandir(year_orders_dir) as months:
    for month in  months:
       if processing.is_json_file(month):
        order_check_rows, item_rows = parse_orders_json(month)
        # print(f"Total rows (valid selections): {len(df)}")
        # print(f"Found in {entry.path}")
        # print(f"Columns: {list(df.columns)}")
        year_order_check_rows += order_check_rows
        year_item_rows += item_rows
        files_processed += 1
  if files_processed == 0:
   raise ValueError(f"No JSON files found in {year_orders_dir}")

  print(f"Total combined rows of orders: {len(year_order_check_rows)}")
  print(f"Total combined rows of ordered items: {len(year_item_rows)}")
  return year_order_check_rows, year_item_rows, files_processed


##__________________LOOP THROUGH A FOLDER of FOLDERS, EACH WITH JSONS________________________________
def parse_orders_json_years(orders_years_dirs: list[str]) -> list[dict]:
  """
  Reads Toast's orders monthly JSON file from multiple year folders into a list of dictionaries, one per item/selection sold.
  Includes voided/deleted orders, checks, and items rather than filtering them out — each is tagged
  with its own boolean flag (order_voided, check_voided, item_voided, order_deleted, check_deleted,
  order_excess_food, is_paid) so downstream reports can filter or audit them explicitly.
  Args:
      orders_years_dirs: list of string paths to each folder containing all JSON files file

  Returns:
      all_rows: List of dictionaries, each one being a DataFrame row.
  """
  all_rows_order_check = []
  all_rows_items = []

  total_files_processed = 0 
  for orders_year_dir  in orders_years_dirs:
    year_order_check_rows, year_item_rows, year_files_processed = parse_orders_json_year(orders_year_dir)
    print(f"Files Processed for directory {orders_year_dir}: ")
    print(f"\t {year_files_processed}")
    all_rows_order_check += year_order_check_rows
    all_rows_items += year_item_rows
    total_files_processed += year_files_processed
  
  print(f"Total Files processed for all the folders: {total_files_processed}")
  return all_rows_order_check, all_rows_items
   

def build_order_dataframe_from_json(rows: list[dict]) -> pd.DataFrame:
    """
    Reads JSON file and builds Datframe
    Args:
      rows: lsit of dictionaries returned by: parse_orders_json_year or parse_orders_json_years

    Returns:
      Dataframe where each item sold is a row.
    """
    if not rows:
      empty = pd.DataFrame(columns=["order_guid", "order_voided", "order_deleted", "order_excess_food",
                                    "number_of_guests", "check_guid", "check_voided", "check_deleted",
                                    "check_net_amount", "yyyyMMdd", "hour", "paid_hour",
                                    "sitting_duration_secs", "dining_option_guid", "revenue_center_guid",
                                    "table_guid"])
      empty["yyyyMMdd"] = pd.to_datetime(empty["yyyyMMdd"])
      return empty

    df = pd.DataFrame(rows)
    df["yyyyMMdd"] = pd.to_datetime(df["yyyyMMdd"].astype(str), format="%Y%m%d", errors="coerce")
    return df

def build_item_by_check_dataframe_from_json(rows: list[dict]) -> pd.DataFrame:
    """
    Reads JSON file and builds Datframe
    Args:
      rows: lsit of dictionaries returned by: parse_orders_json_year or parse_orders_json_years

    Returns:
      Dataframe where each item sold is a row.
    """
    if not rows:
      return pd.DataFrame(columns=["check_guid", "selection_guid", "item_display_name", "item_guid",
                                    "sales_category_guid", "item_voided", "quantity", "price",
                                    "pre_discount_price"])
    return pd.DataFrame(rows)


## _____________________________ COMPLEMENT DFs __________________________________________
def complement_dataframe_calendar(df) -> pd.DataFrame:
  """
  Make extra date columns for KPI calculation
  Args:
    df: DataFrame, to be edited

  Returns:
    df: DataFrame with added columns
  """
  df["year"] = df["yyyyMMdd"].dt.to_period('Y')
  df['year_month'] = df["yyyyMMdd"].dt.to_period('M')
  df['year_week'] = df["yyyyMMdd"].dt.to_period('W')
  return df


def complement_dataframe_item_price_n_discount(df) -> pd.DataFrame:
  """
  Make extra columns for items for KPI calculation
  Args:
    df: DataFrame, to be edited

  Returns:
    df: DataFrame with added columns
  """
  df['unit_price'] = (df['pre_discount_price'] / df['quantity']).where(df['quantity'] != 0)
  df['total_discount'] = df['pre_discount_price'] - df['price']
  df['unit_discount'] = (df['total_discount'] / df['quantity']).where(df['quantity'] != 0)
  return df


def build_item_and_order_dataframes(orders_years_dirs: list[str], order_checks_output_dir: str, items_output_dir: str) -> pd.DataFrame:
  """
  Builds full complemented dataframe with each row having the item sold,
  date, order, check, price, discounts, category, etc. Items can be grouped
  by day to get top/worst items.
  Args:
    orders_years_dirs: list of string paths to each folder containing all JSON files file
    output_dir: directory where to save the DataFrame as CSV ile

  Returns:
    Saves dataframe in output_dir as csv file.
  """
  all_rows_order_check, all_rows_items = parse_orders_json_years(orders_years_dirs)
  orders_checks_df = build_order_dataframe_from_json(all_rows_order_check)
  items_df = build_item_by_check_dataframe_from_json(all_rows_items)

  # Toast's businessDate can extend past local midnight, so an order right at a
  # month boundary (e.g. late on Dec 31) can be returned by both the outgoing and
  # incoming month's API query window in run_order_extraction, producing exact
  # duplicate check/item rows once two monthly JSON files are combined here.
  before_checks = len(orders_checks_df)
  orders_checks_df = orders_checks_df.drop_duplicates(subset=["check_guid"], keep="first")
  if len(orders_checks_df) != before_checks:
    print(f"Dropped {before_checks - len(orders_checks_df)} duplicate check_guid row(s) (month-boundary overlap).")

  before_items = len(items_df)
  items_df = items_df.drop_duplicates(subset=["selection_guid"], keep="first")
  if len(items_df) != before_items:
    print(f"Dropped {before_items - len(items_df)} duplicate selection_guid row(s) (month-boundary overlap).")

  orders_checks_df = complement_dataframe_calendar(orders_checks_df)
  items_df = complement_dataframe_item_price_n_discount(items_df)
  print(f"Columns for orders and checks DataFrame: {list(orders_checks_df.columns)}")
  print(f"Total rows after processing all folders: {len(orders_checks_df)}")
  print(f"Columns for orders and checks DataFrame: {list(items_df.columns)}")
  print(f"Total rows after processing all folders: {len(items_df)}")
  
  orders_checks_df.to_csv(order_checks_output_dir, index=False)
  items_df.to_csv(items_output_dir, index=False)

  print("JSON file turned into CSVs succesfully")


#______________________DAILY SUMMARY EXCLUSIVE FUNCTIONS_________________________________________
def parse_orders_json_daily_summary(filepath: str) -> list[dict]:
  """
  Reads Toast's orders monthly JSON file into a list of dictionaries, one per valid
  (non-voided, paid) ORDER — not per check. Order-level avoids double-counting
  net_sales and guest count on split-bill orders with multiple checks.
  Excludes:
    -> Orders where voided == True, deleted == True, or excessFood == True
    -> Orders with no paidDate (open/test-mode/interrupted orders)
    -> Individual checks where voided == True or deleted == True
  Args:
      filepath: path to the monthly JSON file.

  Returns:
      List of dictionaries, one per valid order:
        {yyyyMMdd, order_guid, net_order_sales, number_of_guests}
  """
  with open(filepath, "r", encoding="utf-8") as f:
      orders = json.load(f)

  rows = []
  skipped_orders = 0

  for order in orders:
      if order.get("voided", False) or order.get("deleted", False) or order.get("excessFood", False):
          skipped_orders += 1
          continue

      paid_date_str = order.get("paidDate")
      if not paid_date_str:
          skipped_orders += 1
          continue

      business_date = order.get("businessDate")
      order_guid = order.get("guid")
      number_of_guests = order.get("numberOfGuests", 0)

      net_order_sales = 0.0
      for check in order.get("checks", []):
          if check.get("voided", False) or check.get("deleted", False):
              continue

          check_net = check.get("amount", 0.0)

          # Only fundraising campaign service charges need subtracting.
          # check.amount already includes everything else correctly.
          for service_charge in check.get("appliedServiceCharges", []) or []:
              if service_charge.get("serviceChargeCategory") == "FUNDRAISING_CAMPAIGN":
                  check_net -= service_charge.get("chargeAmount", 0.0) or 0.0

          net_order_sales += check_net

      rows.append({
          "yyyyMMdd": business_date,
          "order_guid": order_guid,
          "net_order_sales": net_order_sales,
          "number_of_guests": number_of_guests,
      })

  return rows, skipped_orders


def parse_orders_daily_summary_year(year_orders_dir:str) -> list[dict]:
  """
  Reads all Toast's orders monthly JSON file within a year folder into a list of dictionaries, one per valid
  (non-voided, paid) ORDER — not per check. Order-level avoids double-counting
  net_sales and guest count on split-bill orders with multiple checks.
  Excludes:
    -> Orders where voided == True, deleted == True, or excessFood == True
    -> Orders with no paidDate (open/test-mode/interrupted orders)
    -> Individual checks where voided == True or deleted == True
  Args:
      year_orders_dir: string, path to the folder containing all monthly JSON files of a year

  Returns:
      List of dictionaries, each one being a DataFrame row.
  """
  year_rows = []
  files_processed = 0
  year_skipped_orders = 0
  with os.scandir(year_orders_dir) as months:
    for month in  months:
       if processing.is_json_file(month):
        rows, skipped_orders = parse_orders_json_daily_summary(month)
        # print(f"Total rows (valid selections): {len(df)}")
        # print(f"Found in {entry.path}")
        # print(f"Columns: {list(df.columns)}")
        year_rows += rows
        files_processed += 1
        year_skipped_orders += skipped_orders
  if files_processed == 0:
   raise ValueError(f"No JSON files found in {year_orders_dir}")

  print(f"Total rows: {len(year_rows)}")
  print(f"A total of {year_skipped_orders} orders were skipped in: ")
  print(f"{year_orders_dir}")
  return year_rows, files_processed, year_skipped_orders


def parse_orders_daily_summary_years(orders_years_dirs: list[str]) -> list[dict]:
  """
  Reads all Toast's orders monthly JSON files from multiple year folders into a list of dictionaries, one per item/selection sold.
  Args:
      orders_years_dirs: list of string paths to each folder containing all JSON files file

  Returns:
      List of dictionaries, each one being a DataFrame row.
  """
  all_rows = []
  total_files_processed = 0 
  total_skipped_orders = 0
  for orders_year_dir  in orders_years_dirs:
    year_rows, year_files_processed, year_skipped_orders = parse_orders_daily_summary_year(orders_year_dir)
    print(f"Files Processed for directory {orders_year_dir}: ")
    print(f"\t {year_files_processed}")
    all_rows += year_rows
    total_files_processed += year_files_processed
    total_skipped_orders += year_skipped_orders
  
  print(f"Total Files processed for all the folders: {total_files_processed}")
  print(f"Total Orders skipped for all the folders: {total_skipped_orders}")
  return all_rows


def build_daily_sales_dataframe_from_json(rows: list[dict]) -> pd.DataFrame:
  """
  Builds a daily summary DataFrame from a Toast orders monthly JSON file:
  total net sales, number of orders, and number of guests per business date.
  Args:
      orders_filepath: string, path to the monthly JSON file.

  Returns:
      DataFrame indexed by yyyyMMdd with columns: net_sales, number_of_orders, number_of_guests
  """
  if not rows:
    empty = pd.DataFrame(columns=["yyyyMMdd", "net_sales", "number_of_orders", "number_of_guests"])
    empty["yyyyMMdd"] = pd.to_datetime(empty["yyyyMMdd"])
    return empty.set_index("yyyyMMdd")

  df = pd.DataFrame(rows)
  df["yyyyMMdd"] = pd.to_datetime(df["yyyyMMdd"].astype(str), format="%Y%m%d", errors="coerce")

  df = df.groupby("yyyyMMdd").agg(net_sales=("net_order_sales", "sum"),
                                  number_of_orders=("order_guid", "nunique"),
                                  number_of_guests=("number_of_guests", "sum"),)
  return df


def build_daily_sales_dataframe(orders_years_dirs: list[str], output_dir: str, 
                                refunds_df: pd.DataFrame) -> pd.DataFrame:
  """
  Builds a daily summary DataFrame from a Toast orders monthly JSON file:
  total net sales, number of orders, and number of guests per business date.
  Args:
      orders_filepath: string, path to the monthly JSON file.

  Returns:
      DataFrame indexed by yyyyMMdd with columns: net_sales, number_of_orders, number_of_guests
  """
  rows = parse_orders_daily_summary_years(orders_years_dirs)
  df = build_daily_sales_dataframe_from_json(rows)

  refunds_df = refunds_df.copy()
  refunds_df['yyyyMMdd'] = pd.to_datetime(refunds_df['yyyyMMdd'])

  df = df.merge(refunds_df[['yyyyMMdd', 'refund_amount', 'tip_refund_amount']],
                left_on='yyyyMMdd',
                right_on='yyyyMMdd', how='left')

  df['refund_amount'] = df['refund_amount'].fillna(0)
  df['tip_refund_amount'] = df['tip_refund_amount'].fillna(0)
  df['net_sales'] = df['net_sales'] - df['refund_amount'] - df['tip_refund_amount']

  df = df[['yyyyMMdd', 'net_sales', 'number_of_orders', 'number_of_guests']]
  df = coerce_numeric_columns(df, ['net_sales', 'number_of_orders', 'number_of_guests'])
  print(f"Columns: {list(df.columns)}")
  print(f"Total rows after processing all folders: {len(df)}")
  df.to_csv(output_dir, index=False)
  print("JSON file turned into CSV succesfully")
  return df


#___________________HOURLY SUMMARY EXCLUSIVE FUNCTIONS_______________________________
def parse_orders_hourly_sales_json(filepath: str) -> list[dict]:
   """
    Reads Toast's orders monthly JSON file into a list of dictionaries, one per valid
    (non-voided, non-deleted, paid) ORDER, tagged with the local hour it was paid in.
    Args:
        filepath: string, path to the monthly JSON file

    Returns:
        List of dictionaries, each one being a DataFrame row: {yyyyMMdd, hour, order_guid,
        net_order_sales, number_of_guests}
    """
   # IANA timezone string for the restaurant's physical location.
   # To avoid a fixed UTC offset (e.g. -5), ZoneInfo automatically switches between standard and daylight saving time.
   # Full timezone list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
   RESTAURANT_TIMEZONE = "America/Chicago"  # Central Time (CST/CDT)

   # Create a timezone object once and reuse it for every timestamp conversion below.
   LOCAL_TZ = ZoneInfo(RESTAURANT_TIMEZONE)

   # Will hold one dict per valid (non-voided) order: {hour, net_sales}
   hour_records = []

   with open(filepath, "r", encoding="utf-8") as f:
       orders = json.load(f)

   for order in orders:
    # Skip voided orders — they were cancelled and generated no revenue.
    if order.get("voided", False) or order.get("deleted", False) or order.get("excessFood", False):
      continue

    # paidDate = the moment the order was closed/paid.
    # This is the right timestamp for "what hour did this sale happen."
    # (openedDate = when the table was seated, which is always earlier.)
    paid_date_str = order.get("paidDate")
    if not paid_date_str:
      continue

    business_date = order.get("businessDate")
    order_guid = order.get("guid")
    number_of_guests = order.get("numberOfGuests")

    # Toast stores all timestamps in UTC (the +0000 suffix in the string).
    # strptime parses the string into a timezone-aware datetime object (UTC).
    # astimezone(LOCAL_TZ) converts it to restaurant local time, applying DST.
    # .hour extracts the integer hour (0–23) in local time.
    hour = datetime.strptime(paid_date_str, "%Y-%m-%dT%H:%M:%S.%f%z") \
                        .astimezone(LOCAL_TZ) \
                        .hour

    # An order can have multiple checks (e.g., a split bill).
    # amount = net sales (pre-tax subtotal). Use totalAmount to include tax.
    # We skip any check that was individually voided within the order.
    net_sales = 0.0

    for check in order.get("checks", []):
      if check.get("voided", False) or check.get("deleted", False):
        continue

      check_net = check.get("amount", 0.0)

      # Only fundraising campaign service charges need subtracting.
      # check.amount already includes everything else correctly.
      for service_charge in check.get("appliedServiceCharges", []) or []:
        if service_charge.get("serviceChargeCategory") == "FUNDRAISING_CAMPAIGN":
          check_net -= service_charge.get("chargeAmount", 0.0) or 0.0

      net_sales += check_net

    # One record per order — appended once all of the order's checks are summed,
    # so split-bill orders don't produce multiple rows with cumulative totals.
    hour_records.append({"yyyyMMdd": business_date, "hour": hour,
                         "order_guid": order_guid, "net_order_sales": net_sales,
                         "number_of_guests": number_of_guests})
    
   return hour_records


def parse_orders_hourly_sales_year(year_orders_dir:str) -> list[dict]:
  """
  Reads all Toast's orders monthly JSON files within a year folder into a list of dictionaries, one per item/selection sold.
  Includes voided/deleted orders, checks, and items rather than filtering them out — each is tagged
  with its own boolean flag (order_voided, check_voided, item_voided, order_deleted, check_deleted,
  order_excess_food, is_paid) so downstream reports can filter or audit them explicitly.
  Args:
      year_orders_dir: string, path to the folder containing all monthly JSON files of a year

  Returns:
      List of dictionaries, each one being a DataFrame row.
  """
  year_rows = []
  files_processed = 0
  with os.scandir(year_orders_dir) as months:
    for month in  months:
       if processing.is_json_file(month):
        rows = parse_orders_hourly_sales_json(month)
        # print(f"Total rows (valid selections): {len(df)}")
        # print(f"Found in {entry.path}")
        # print(f"Columns: {list(df.columns)}")
        year_rows += rows
        files_processed += 1
  if files_processed == 0:
   raise ValueError(f"No JSON files found in {year_orders_dir}")

  print(f"Total rows: {len(year_rows)}")
  return year_rows, files_processed

def parse_orders_hourly_sales_years(orders_years_dirs: list[str]) -> list[dict]:
  """
  Reads all Toast's orders monthly JSON files from multiple year folders into a list of dictionaries, one per item/selection sold.
  Includes voided/deleted orders, checks, and items rather than filtering them out — each is tagged
  with its own boolean flag (order_voided, check_voided, item_voided, order_deleted, check_deleted,
  order_excess_food, is_paid) so downstream reports can filter or audit them explicitly.
  Args:
      orders_years_dirs: list of string paths to each folder containing all JSON files file

  Returns:
      List of dictionaries, each one being a DataFrame row.
  """
  all_rows = []
  total_files_processed = 0 
  for orders_year_dir  in orders_years_dirs:
    year_rows, year_files_processed = parse_orders_hourly_sales_year(orders_year_dir)
    print(f"Files Processed for directory {orders_year_dir}: ")
    print(f"\t {year_files_processed}")
    all_rows += year_rows
    total_files_processed += year_files_processed
  
  print(f"Total Files processed for all the folders: {total_files_processed}")
  return all_rows


def build_hourly_sales_dataframe_from_json(rows: list[dict]) -> pd.DataFrame:
    """
    Reads JSON file and builds Datframe
    Args:
      rows: lsit of dictionaries returned by: parse_orders_json_year or parse_orders_json_years

    Returns:
      df: Dataframe where each item sold is as hour with its respective sales.
    """
    # Build a flat DataFrame from the collected records.
    # Named df_hours to avoid overwriting the item-level `df` built in cells above.
    if not rows:
      empty = pd.DataFrame(columns=["yyyyMMdd", "hour", "order_guid", "net_order_sales",
                                    "number_of_guests", "Hour Label"])
      empty["yyyyMMdd"] = pd.to_datetime(empty["yyyyMMdd"])
      return empty

    df = pd.DataFrame(rows)

    # # Group by hour, summing net_sales across all orders that closed in that hour.
    # # as_index=False keeps `hour` as a regular column rather than the DataFrame index.
    # sales_by_hour = (
    #     df_hours.groupby("hour", as_index=False)["net_sales"]
    #     .sum()
    #     .rename(columns={"hour": "Hour", "net_sales": "Net Sales ($)"})
    #     .sort_values("Hour")        # ensure rows run 0, 1, 2, ... 23
    #     .reset_index(drop=True)
    # )

    # Human-readable label for Power BI visuals (e.g. hour 14 → "2 PM").
    # `h % 12 or 12` maps 0 → 12 and 13 → 1 for standard 12-hour clock format.
    df["Hour Label"] = df["hour"].apply( lambda h: f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}")

    # print(f"Sales by Hour ({RESTAURANT_TIMEZONE}) — {len(df_hours):,} valid orders processed\n")
    # print(sales_by_hour[["Hour", "Hour Label", "Net Sales ($)"]].to_string(index=False))
    df["yyyyMMdd"] = pd.to_datetime(df["yyyyMMdd"].astype(str), format="%Y%m%d", errors="coerce")
    #df.to_csv(output_path, index=False)
    ## Export to CSV for Power BI import.
    return df


def build_hourly_sales_dataframe(orders_years_dirs: list[str], output_dir: str) -> pd.DataFrame:
  """
    Reads Toast's orders monthly JSON file into a list of dictionaries, one per valid
    (non-voided, non-deleted, paid) ORDER, tagged with the local hour it was paid in.
    Args:
        filepath: string, path to the monthly JSON file

    Returns:
        List of dictionaries, each one being a DataFrame row: {yyyyMMdd, hour, order_guid,
        net_order_sales, number_of_guests}
  """
  rows = parse_orders_hourly_sales_years(orders_years_dirs)
  df = build_hourly_sales_dataframe_from_json(rows)
  df = complement_dataframe_calendar(df)
  print(f"Columns: {list(df.columns)}")
  print(f"Total rows after processing all folders: {len(df)}")
  df.to_csv(output_dir, index=False)
  print("JSON file turned into CSV succesfully")
  return df


def _parse_orders_hourly_json_sales(filepath: str) -> pd.DataFrame:
    """
    Reads Toast's orders monthly JSON file into a list of dictionaries, one per valid
    (non-voided, non-deleted, paid) ORDER, tagged with the local hour it was paid in.
    Args:
        filepath: string, path to the monthly JSON file

    Returns:
        List of dictionaries, each one being a DataFrame row: {yyyyMMdd, hour, order_guid,
        net_order_sales, number_of_guests}
    """
    # IANA timezone string for the restaurant's physical location.
    # To avoid a fixed UTC offset (e.g. -5), ZoneInfo automatically switches between standard and daylight saving time.
    # Full timezone list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    RESTAURANT_TIMEZONE = "America/Chicago"  # Central Time (CST/CDT)


    # Create a timezone object once and reuse it for every timestamp conversion below.
    LOCAL_TZ = ZoneInfo(RESTAURANT_TIMEZONE)

    # Will hold one dict per valid (non-voided) order: {hour, net_sales}
    hour_records = []

    with open(filepath, "r", encoding="utf-8") as f:
        orders = json.load(f)

    for order in orders:
        # Skip voided orders — they were cancelled and generated no revenue.
        if order.get("voided", False) or order.get("deleted", False) or order.get("excessFood", False):
          continue

        # paidDate = the moment the order was closed/paid.
        # This is the right timestamp for "what hour did this sale happen."
        # (openedDate = when the table was seated, which is always earlier.)
        paid_date_str = order.get("paidDate")
        if not paid_date_str:
            continue

        business_date = order.get("businessDate")
        order_guid = order.get("guid")
        number_of_guests = order.get("numberOfGuests")

        # Toast stores all timestamps in UTC (the +0000 suffix in the string).
        # strptime parses the string into a timezone-aware datetime object (UTC).
        # astimezone(LOCAL_TZ) converts it to restaurant local time, applying DST.
        # .hour extracts the integer hour (0–23) in local time.
        hour = datetime.strptime(paid_date_str, "%Y-%m-%dT%H:%M:%S.%f%z") \
                        .astimezone(LOCAL_TZ) \
                        .hour

        # An order can have multiple checks (e.g., a split bill).
        # amount = net sales (pre-tax subtotal). Use totalAmount to include tax.
        # We skip any check that was individually voided within the order.
        net_sales = 0.0

        for check in order.get("checks", []):
            if check.get("voided", False) or check.get("deleted", False):
              continue

            check_net = check.get("amount", 0.0)

            # Only fundraising campaign service charges need subtracting.
            # check.amount already includes everything else correctly.
            for service_charge in check.get("appliedServiceCharges", []) or []:
                if service_charge.get("serviceChargeCategory") == "FUNDRAISING_CAMPAIGN":
                    check_net -= service_charge.get("chargeAmount", 0.0) or 0.0

            net_sales += check_net

        # One record per order — appended once all of the order's checks are summed,
        # so split-bill orders don't produce multiple rows with cumulative totals.
        hour_records.append({"yyyyMMdd": business_date, "hour": hour,
                             "order_guid": order_guid, "net_order_sales": net_sales,
                             "number_of_guests": number_of_guests})

    # Build a flat DataFrame from the collected records.
    # Named df_hours to avoid overwriting the item-level `df` built in cells above.
    df_hours = pd.DataFrame(hour_records)

    # # Group by hour, summing net_sales across all orders that closed in that hour.
    # # as_index=False keeps `hour` as a regular column rather than the DataFrame index.
    # sales_by_hour = (
    #     df_hours.groupby("hour", as_index=False)["net_sales"]
    #     .sum()
    #     .rename(columns={"hour": "Hour", "net_sales": "Net Sales ($)"})
    #     .sort_values("Hour")        # ensure rows run 0, 1, 2, ... 23
    #     .reset_index(drop=True)
    # )

    # Human-readable label for Power BI visuals (e.g. hour 14 → "2 PM").
    # `h % 12 or 12` maps 0 → 12 and 13 → 1 for standard 12-hour clock format.
    df_hours["Hour Label"] = df_hours["hour"].apply( lambda h: f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}")

    # print(f"Sales by Hour ({RESTAURANT_TIMEZONE}) — {len(df_hours):,} valid orders processed\n")
    # print(sales_by_hour[["Hour", "Hour Label", "Net Sales ($)"]].to_string(index=False))
    df_hours["yyyyMMdd"] = pd.to_datetime(df_hours["yyyyMMdd"].astype(str), format="%Y%m%d", errors="coerce")

    df_hours = complement_dataframe_calendar(df_hours)
    #df_hours.to_csv(output_path, index=False)
    ## Export to CSV for Power BI import.
    return df_hours

def _build_sales_by_day_hour_dataframe(json_folder_dir: str, output_dir: str) -> pd.DataFrame:
  """
  Builds a sales by day approximation report that mimicks TOAST's report under the same name.
  Args:
    json_folder_dir: path to the folder containing all the JSONS to be merged and
    turned into Dataframe

    output_dir: directory where to save the DataFrame as CSV ile

  Returns:
    Saves dataframe in output_dir as csv file.
  """
  dfs = []

  with os.scandir(json_folder_dir) as entries:
    for entry in entries:
      if processing.is_json_file(entry):
        df = _parse_orders_hourly_json_sales(entry)
        # print(f"Total rows (valid selections): {len(df)}")
        # print(f"Found in {entry.path}")
        # print(f"Columns: {list(df.columns)}")
        dfs.append(df)

  if not dfs:
    raise ValueError(f"No JSON files found in {json_folder_dir}")

  df = pd.concat(dfs, ignore_index=True)
  df.to_csv(output_dir, index=False)
  return df

############ MONTHLY SUMMARY EXCLUSIVE FUNCTIONS ####################

def build_monthly_sales_df(daily_sales_df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
  """
  Aggregates a daily sales DataFrame into one row per month, with month-over-month
  sales growth.

  Args:
    daily_sales_df: DataFrame with a "yyyyMMdd" date column and a "net_sales" column
      (e.g., the output of build_daily_sales_dataframe).
    output_dir: string, path to write the monthly sales CSV to.

  Returns:
    df: DataFrame indexed by year_month with net_sales, prev Net sales, sales growth.
    Note: "yyyyMMdd" here holds the year_month Period (e.g. "2025-01"), not a daily
    date like in the daily/item-level DataFrames — same column name, coarser granularity.
  """
  daily_sales_df['yyyyMMdd'] = pd.to_datetime(daily_sales_df['yyyyMMdd'].astype(str), format='mixed', errors='coerce')
  daily_sales_df['year_month'] = daily_sales_df['yyyyMMdd'].dt.to_period('M')
  daily_sales_df['year_week'] = daily_sales_df["yyyyMMdd"].dt.to_period('W')
  daily_sales_df = daily_sales_df.groupby("year_month").sum(numeric_only = True)
  daily_sales_df['prev Net sales'] = daily_sales_df['net_sales'].shift(1)
  daily_sales_df['sales growth'] = 100 * (daily_sales_df['net_sales'] - daily_sales_df['prev Net sales']) / daily_sales_df['prev Net sales']
  daily_sales_df['yyyyMMdd'] = daily_sales_df.index
  daily_sales_df.to_csv(output_dir, index=False)
  return daily_sales_df
