import os
import json
import pandas as pd
import general_data_processing as processing 


##____________________________HELPER FUNCTIONS___________________________________________________
def flatten_order_detail(order_detail: dict) -> tuple[dict, list[dict]]:
  """
  Splits one order detail response into:
  - order_row: order-level dict (the authoritative $ figures)
  - line_item_rows: list of per-line-item dicts

  Args:
    order_detail: dict returned from get_single_order_details()

  Returns:
    order_row: dict with the order's details
    line_item_rows: list of dicts, one per item included in the order
  """
  order_id = order_detail.get("orderId")

  order_row = {
      "order_id": order_id,
      "vendor_id": order_detail.get("vendorId"),
      "vendor_name": order_detail.get("vendorName"),
      "invoice_number": order_detail.get("invoiceNumber"),
      "customer_number": order_detail.get("customerNumber"),
      "invoice_date": order_detail.get("invoiceDate"),
      "created_date": order_detail.get("createdDate"),
      "status": order_detail.get("status"),
      "payment_account": order_detail.get("paymentAccount"),
      "order_total": order_detail.get("orderTotal"),
      "tax": order_detail.get("tax"),
      "delivery_charges": order_detail.get("deliveryCharges"),
      "other_charges": order_detail.get("otherCharges"),
      "other_description": order_detail.get("otherDescription"),
      "credit_amount": order_detail.get("creditAmount"),
      "is_credit": order_detail.get("isCredit", False),
      "input_tax_credits": order_detail.get("inputTaxCredits"),
      }

  line_item_rows = []
  for idx, item in enumerate(order_detail.get("lineItems", [])):
    is_category_level = item.get("vendorItemCode") is None and item.get("categoryId") is not None
    line_item_rows.append({"order_id": order_id,
                           "line_item_index": idx + 1, 
                           "is_category_level": is_category_level,
                           "category_id": item.get("categoryId"),
                           "vendor_item_code": item.get("vendorItemCode"),
                           "vendor_item_name": item.get("vendorItemName"),
                           "company_concept_product_id": item.get("companyConceptProductId"),
                           "packaging_id": item.get("packagingId"),
                           "quantity": item.get("quantity"),
                           "unit_price": item.get("unitPrice"),
                           "line_price": item.get("linePrice"),
                           })
  return order_row, line_item_rows


##____________________________ Reading raw JSON into flat rows____________________________
def extract_order_rows_from_file(filepath: str) -> tuple[list[dict], list[dict]]:
    """
    Reads one month's raw order-detail JSON (as saved by run_marginedge_extraction)
    and flattens it into order-level rows and line-item rows.

    Args:
      filepath: string, path to a marginedge_orders_{year}_{month}.json file

    Returns:
      order_rows: list of dicts, one per order
      line_item_rows: list of dicts, one per line item across all orders in the file
    """
    with open(filepath, "r", encoding="utf-8") as f:
        order_details = json.load(f)

    order_rows, line_item_rows = [], []
    for detail in order_details or []:
        o_row, li_rows = flatten_order_detail(detail)
        order_rows.append(o_row)
        line_item_rows.extend(li_rows)

    return order_rows, line_item_rows

def extract_order_rows_from_folder(marginedge_dir: str) -> tuple[list[dict], list[dict]]:
    """
    Build rows for all monthly MarginEdge JSON files found in a directory.
    Args:
      marginedge_dir: string, folder containing marginedge_orders_*.json files

    Returns:
      order_rows, line_item_rows across all files in the directory.
    """
    all_order_rows, all_line_item_rows = [], []
    found_json = False

    with os.scandir(marginedge_dir) as entries:
        for entry in entries:
            if processing.is_json_file(entry):
                found_json = True
                o_rows, li_rows = extract_order_rows_from_file(entry.path)
                all_order_rows += o_rows
                all_line_item_rows += li_rows

    if not found_json:
        print("No JSON files found!!!!!")

    return all_order_rows, all_line_item_rows


def extract_order_rows_from_folders(marginedge_dirs: list[str]) -> tuple[list[dict], list[dict]]:
    """
    Same as extract_order_rows_from_folder but across multiple directories
    (e.g., one folder per year of exports).
    """
    all_order_rows, all_line_item_rows = [], []
    for marginedge_dir in marginedge_dirs:
        o_rows, li_rows = extract_order_rows_from_folder(marginedge_dir)
        all_order_rows += o_rows
        all_line_item_rows += li_rows
    return all_order_rows, all_line_item_rows


##____________________________ Date complements ____________________________
def complement_dataframe_with_dates(df:pd.DataFrame, date_column:str="invoice_date") -> pd.DataFrame:
    """
    Adds yyyyMMdd/year/year_month/year_week columns, matching the same pattern as
    complement_dataframe_with_dates in json_processing_toast_labor.py.

    IMPORTANT: uses invoice_date, NOT created_date -- invoiceDate is the period the
    expense actually belongs to; createdDate is just the upload date into MarginEdge.

    Args:
      df: DataFrame with a date_column (default "invoice_date")
      date_column: which column to build yyyyMMdd from

    Returns:
      df with yyyyMMdd (datetime), year, year_month, year_week columns added.
    """
    if not processing.column_exists(df, date_column):
        raise ValueError(f"Dataframe provided lacks a date column '{date_column}'.")

    df["yyyyMMdd"] = pd.to_datetime(df[date_column], errors="coerce")
    df["year"] = df["yyyyMMdd"].dt.to_period("Y")
    df["year_month"] = df["yyyyMMdd"].dt.to_period("M")
    df["year_week"] = df["yyyyMMdd"].dt.to_period("W")
    return df


def complement_marginedge_orders(orders_df: pd.DataFrame) -> pd.DataFrame:
    """
    Sign-flips credit memo orders so order_total (the authoritative spend figure)
    correctly REDUCES total purchases when summed, instead of adding to them.

    ASSUMPTION NOT YET VALIDATED: this assumes the API returns order_total as a
    positive magnitude even for credit memos (is_credit == True). Confirm against
    an actual is_credit==True row from real data before trusting aggregated
    totals -- same "validate against real data" principle as the Toast
    check.amount undercount lesson.

    Args:
      orders_df: DataFrame built from extract_order_rows_from_file/folder(s)

    Returns:
      orders_df with money columns negated for is_credit==True rows that aren't
      already negative.
    """
    money_cols = ["order_total", "tax", "delivery_charges", "other_charges", "credit_amount"]
    is_credit = orders_df["is_credit"] == True

    for col in money_cols:
        if col in orders_df.columns:
            already_negative = orders_df[col] < 0
            flip = is_credit & ~already_negative & orders_df[col].notna()
            orders_df.loc[flip, col] = -orders_df.loc[flip, col]

    return orders_df


##____________________________ Builder____________________________
def build_marginedge_dataframes(marginedge_dirs, orders_output_path: str, line_items_output_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Args:
      marginedge_dirs: string (single folder) or list of strings (e.g., one folder
        per year), each containing marginedge_orders_{year}_{month}.json files.
      orders_output_path: string, path to write the combined orders CSV to.
      line_items_output_path: string, path to write the combined line-items CSV to.

    Returns:
      orders_df: combined, date-enriched, sign-flipped order-level DataFrame.
      line_items_df: combined line-item-level DataFrame (category/vendor breakdowns).
      NOTE: orders_df["order_total"] is the authoritative $ figure -- SUM of
      line_items_df["line_price"] will NOT reconstruct it (same undercount risk
      pattern documented for Toast's check.amount).
    """
    if isinstance(marginedge_dirs, str):
        marginedge_dirs = [marginedge_dirs]

    order_rows, line_item_rows = extract_order_rows_from_folders(marginedge_dirs)

    ORDER_COLUMNS = ["order_id", "vendor_id", "vendor_name", "invoice_number", "customer_number",
                     "invoice_date", "created_date", "status", "payment_account", "order_total",
                     "tax", "delivery_charges", "other_charges", "other_description",
                     "credit_amount", "is_credit", "input_tax_credits"]
    LINE_ITEM_COLUMNS = ["order_id", "line_item_index", "is_category_level", "category_id",
                         "vendor_item_code", "vendor_item_name", "company_concept_product_id",
                         "packaging_id", "quantity", "unit_price", "line_price"]

    orders_df = pd.DataFrame(order_rows, columns=ORDER_COLUMNS)
    line_items_df = pd.DataFrame(line_item_rows, columns=LINE_ITEM_COLUMNS)

    orders_df = complement_dataframe_with_dates(orders_df, date_column="invoice_date")
    orders_df = complement_marginedge_orders(orders_df)

    orders_df.to_csv(orders_output_path, index=False)
    line_items_df.to_csv(line_items_output_path, index=False)

    return orders_df, line_items_df


##____________________________ Catalog JSON -> CSV builders____________________________
VENDOR_COLUMNS_RENAME = {
    "vendorId": "vendor_id",
    "centralVendorId": "central_vendor_id",
    "vendorName": "vendor_name",
    "vendorAccounts": "vendor_accounts",
}

CATEGORY_COLUMNS_RENAME = {
    "categoryId": "category_id",
    "categoryName": "category_name",
    "categoryType": "category_type",
    "accountingCode": "accounting_code",
}

def build_dataframe_from_json_vendors(json_path: str, output_csv_path: str) -> None:
    """
    Reads catalog_vendors.json and writes it out as catalog_vendors.csv,
    with columns renamed to snake_case to match catalog_vendors in Neon.
    Args:
      json_path: path to catalog_vendors.json
      output_csv_path: path to write the CSV to
    Returns:
      None
    """
    with open(json_path, "r", encoding="utf-8") as f:
        vendors = json.load(f)
    pd.DataFrame(vendors).rename(columns=VENDOR_COLUMNS_RENAME).to_csv(output_csv_path, index=False)


def build_dataframe_from_json_categories(json_path: str, output_csv_path: str) -> None:
    """
    Reads catalog_categories.json and writes it out as catalog_categories.csv,
    with columns renamed to snake_case to match catalog_purchase_categories in Neon.
    Args:
      json_path: path to catalog_categories.json
      output_csv_path: path to write the CSV to
    Returns:
      None
    """
    with open(json_path, "r", encoding="utf-8") as f:
        categories = json.load(f)
    pd.DataFrame(categories).rename(columns=CATEGORY_COLUMNS_RENAME).to_csv(output_csv_path, index=False)
 
 
def build_dataframe_from_json_restaurant_units(json_path: str, output_csv_path: str) -> None:
    """
    Reads catalog_restaurant_units.json and writes it out as catalog_restaurant_units.csv.
    Args:
      json_path: path to catalog_restaurant_units.json
      output_csv_path: path to write the CSV to
    Returns:
      None
    """
    with open(json_path, "r", encoding="utf-8") as f:
        units = json.load(f)
    pd.DataFrame(units).to_csv(output_csv_path, index=False)