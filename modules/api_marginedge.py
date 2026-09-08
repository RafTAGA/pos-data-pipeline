import os
import time
import json
import requests # type: ignore
from datetime import date
import general_data_processing as processing # type: ignore

BASE_URL = "https://api.marginedge.com/public"
AUTH_HEADER_NAME = "X-Api-Key"  # confirmed from developer portal
RATE_LIMIT_SECONDS = 1.05 
REPORTABLE_STATUSES = {"CLOSED"}

##____________________________GENERAL API SUPPORTING FUNCTIONS___________________________________________________
def _headers(api_key:str) -> dict:
  """
  Get the call headers using the API_KEY, raise error if none is available
  Args:
    api_key = string to the MarginEdge API key, available at MarginEdge "Access" Page.

  Returns:
    None
  """
  if not api_key:
    raise RuntimeError("MARGINEDGE_API_KEY not set. Set os.environ['MARGINEDGE_API_KEY'] = '...' "
                       "(or Colab userdata) before calling any extraction functions.")
  return {AUTH_HEADER_NAME: api_key}


def _get(endpoint:str, api_key: str, params:dict|None=None) -> dict:
    """
    Single rate-limited GET with retry for 429 Too Many Requests.
    Sleeps BEFORE the call so retries don't skip the limit.
    Args:
      endpoint: target endpoint call, listed at https://developer.marginedge.com/#/guide/api_overview
      api_key: MarginEdge API key, threaded through explicitly (no module-level global --
               this module runs unattended in GitHub Actions with the key from GitHub
               Secrets, same convention as api_toast.py).
      params: dict of desired params for the endpoint; see https://developer.marginedge.com/#/api_reference

    Returns:
      resp: parsed JSON response as a dict
    """
    MAX_RETRIES = 5
    resp = None
    for attempt in range(MAX_RETRIES):
        time.sleep(RATE_LIMIT_SECONDS)  # Adhere to global rate limit
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=_headers(api_key), params=params or {})

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:  # Too Many Requests - Rate Limit Exceeded
            wait_time = 2 ** attempt
            print(f"Rate limit hit for {endpoint}. Retrying in {wait_time} seconds (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_time)
        elif resp.status_code == 401:
            raise RuntimeError(f"401 Unauthorized on {endpoint}: check MARGINEDGE_API_KEY value.")
        elif resp.status_code == 403:
            raise RuntimeError(
                f"403 Forbidden on {endpoint}: key may not be scoped to this restaurantUnitId, "
                f"or the restaurant isn't enabled for public API access."
            )
        elif resp.status_code >= 500:
            wait_time = 2 ** attempt
            print(f"Server error ({resp.status_code}) for {endpoint}. Retrying in {wait_time} seconds (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_time)
        else:
            resp.raise_for_status()
            return resp.json()

    resp.raise_for_status()
    return resp.json()


def _paginate(endpoint:str, list_key:str, api_key:str, params:dict|None=None):
  """
  Cursor-based pagination generator. Yields items from `list_key` across all pages.
  Stops when the response's nextPage is missing/empty.
  Args:
    endpoint: target endpoint call
    list_key: the endpoint's list key returned alongside "nextPage"
    api_key: MarginEdge API key
    params: dict of desired params for the endpoint

  Returns:
    None
  """
  params = dict(params or {})
  while True:
    page = _get(endpoint, api_key, params)
    yield from page.get(list_key, []) #Extract all items in the listkey per page.

    next_page = page.get("nextPage")
    if not next_page:
      break
    params["nextPage"] = next_page



##____________________________MARGINEDGE CATALOG EXTRACTION (dimension/lookup tables)___________________________________________________
def run_marginedge_catalog_extraction(api_key: str, restaurant_unit_id: str, output_dir: str) -> None:
    """
    Extracts MarginEdge dimension/lookup data (restaurant units, vendors, categories)
    and saves each as raw JSON, mirroring api_toast.py's run_catalog_extraction.

    These are current-state snapshots, not date-ranged -- re-run periodically to
    pick up newly added vendors/categories rather than treating this as one-time.
    No skip-if-exists here (unlike the monthly order/labor extraction) since a
    snapshot should always be freshly pulled, not cached indefinitely.

    Args:
      api_key: MarginEdge API key
      restaurant_unit_id: MarginEdge restaurantUnitId, e.g. RESTAURANT_UNIT_ID
      output_dir: folder to save catalog_*.json files into

    Returns:
      None. Saves catalog_restaurant_units.json, catalog_vendors.json,
      catalog_categories.json to output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Restaurant units aren't scoped to a single restaurant -- fetched once, no pagination.
    units_data = _get("/restaurantUnits", api_key)
    units = units_data.get("restaurants", [])
    with open(os.path.join(output_dir, "catalog_restaurant_units.json"), "w", encoding="utf-8") as f:
        json.dump(units, f, ensure_ascii=False, indent=2)
    print(f"[restaurantUnits] Saved: {len(units)} records")

    vendors = list(_paginate("/vendors", "vendors", api_key, {"restaurantUnitId": restaurant_unit_id}))
    with open(os.path.join(output_dir, "catalog_vendors.json"), "w", encoding="utf-8") as f:
        json.dump(vendors, f, ensure_ascii=False, indent=2)
    print(f"[vendors] Saved: {len(vendors)} records")

    categories = list(_paginate("/categories", "categories", api_key, {"restaurantUnitId": restaurant_unit_id}))
    with open(os.path.join(output_dir, "catalog_categories.json"), "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print(f"[categories] Saved: {len(categories)} records")

    print("MarginEdge catalog extraction complete!")



## ____________________________MARGINEDGE Get orders list_________________________________________________
def get_orders_list(restaurant_unit_id: str, start_date: date, end_date: date,
                     api_key: str, status: str = "CLOSED") -> list[dict]:
    """
    Summary rows for orders CREATED (uploaded) within [start_date, end_date] in
    the given status. Note createdDate != invoiceDate -- createdDate is upload date.
    For revenue-period matching, filter/group by invoiceDate from order DETAIL,
    not createdDate from this list call.

    Args:
      restaurant_unit_id: target restaurant's id
      start_date: start date of the desired range
      end_date: end date of the desired range
      api_key: MarginEdge API key
      status: order status, CLOSED by default (finalized orders only)

    Returns:
      List of raw order-summary dicts (each includes orderId) for the range.
      Returns a list, not a DataFrame, so callers doing simple ID extraction
      (extract_expenses, run_marginedge_extraction) don't pay for a DataFrame
      wrap-and-unwrap just to pull out order IDs. Wrap in pd.DataFrame(rows)
      yourself if you want a table for notebook inspection.
    """
    params = {
        "restaurantUnitId": restaurant_unit_id,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "orderStatus": status,
    }
    rows = list(_paginate("/orders", "orders", api_key, params))
    print(f"{len(rows)} orders found ({start_date} to {end_date}, status={status})")
    return rows

def get_single_order_details(order_id: int, restaurant_unit_id: str, api_key: str) -> dict:
  """
  Full details for one order, including line items, charge per item, and order-level charges.
  Args:
    order_id: order identifier
    restaurant_unit_id: restaurant unique identifier
    api_key: MarginEdge API key

  Returns:
    dict with all order details (raw, unflattened)
  """
  return _get(f"/orders/{order_id}", api_key, {"restaurantUnitId": restaurant_unit_id})


def run_marginedge_extraction(api_key: str, restaurant_unit_id: str,
                               start_date: tuple, end_date: tuple,
                               output_dir: str, status: str = "CLOSED") -> None:
    """
    Extracts MarginEdge orders between (start_date, end_date) inclusive, one
    calendar-month segment at a time (clipped to the exact days requested),
    saving each segment's RAW order-detail JSON to its own file. Mirrors
    api_toast.py's run_order_extraction structure: skip-if-exists, N+1 call
    pattern. Rate limiting and 429/5xx retry/backoff are handled inside
    _get() -- no extra sleep needed here.

    Unlike Toast's /labor/v1/timeEntries, MarginEdge documents no hard date-range
    cap, so monthly chunking here is purely for resumability and audit-trail
    granularity (a failed run only needs to re-pull the segment it stopped on), not
    to respect an API limit.

    Args:
      api_key: MarginEdge API key (MARGINEDGE_API_KEY)
      restaurant_unit_id: MarginEdge restaurantUnitId, e.g. RESTAURANT_UNIT_ID
      start_date: tuple (year, month, day), inclusive start
      end_date: tuple (year, month, day), inclusive end
      output_dir: folder to save one JSON file per segment
      status: order status filter, "CLOSED" by default (finalized orders only)

    Returns:
      None. Saves one JSON file per calendar-month segment: whole-month requests
      keep marginedge_orders_{year}_{month:02d}.json (unchanged from before
      day-level extraction), partial ranges get marginedge_orders_{year}_{month:02d}_{d1}to{d2}.json,
      each a list of RAW, unflattened order-detail dicts (Toast's raw-JSON-first
      pattern) -- flattening into order_df/line_items_df happens separately in
      json_processing_marginedge.py.
    """
    os.makedirs(output_dir, exist_ok=True)

    for year, month, day_start, day_end, is_full_month in processing.month_chunks(start_date=date(*start_date), end_date=date(*end_date)):
        label = f"{year}_{month:02d}" if is_full_month else f"{year}_{month:02d}_{day_start:02d}to{day_end:02d}"
        output_path = os.path.join(output_dir, f"marginedge_orders_{label}.json")

        if os.path.exists(output_path):
            print(f"[{label}] Already extracted, skipping.")
            continue

        print(f"\nExtracting MarginEdge orders for [{label}]...")
        start_dt, end_dt = date(year, month, day_start), date(year, month, day_end)

        try:
            orders_summary = get_orders_list(
                restaurant_unit_id=restaurant_unit_id,
                start_date=start_dt,
                end_date=end_dt,
                api_key=api_key,
                status=status,
            )
            order_ids = [row["orderId"] for row in orders_summary if "orderId" in row]

            order_details = []
            for idx, order_id in enumerate(order_ids):
                detail = get_single_order_details(order_id, restaurant_unit_id, api_key)
                order_details.append(detail)

                if (idx + 1) % 25 == 0:
                    print(f"  [{label}] ...{idx + 1}/{len(order_ids)} invoices fetched")

        except requests.exceptions.HTTPError as e:
            print(f"[{label}] ERROR: {e}")
            print("Stopping extraction due to ERROR. Please review the ERROR.")
            break

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(order_details, f, ensure_ascii=False, indent=2)

        print(f"[{label}] Saved: {len(order_details)} order details to {output_path}")

    print("\nMARGINEDGE EXTRACTION COMPLETE or STOPPED BY ERROR, CONFIRM WITH LOGS!")

# def flatten_order_detail(order_detail: dict) -> tuple[dict, list[dict]]:
#   """
#   Splits one order detail response into:
#   - order_row: order-level dict (the authoritative $ figures)
#   - line_item_rows: list of per-line-item dicts

#   Args:
#     order_detail: dictionary retunred from: get_single_order_details()

#   Returns:
#     order_row: dictionary with all the order's details
#     line_item_rows: list of dictionatries with details of items included in the order.
#   """
#   order_id = order_detail.get("orderId")

#   ## dict.get(key_name) returns None instead of KeyError when called key_name is not found in the dict
#   order_row = {
#       "order_id": order_id,
#       "vendor_id": order_detail.get("vendorId"),
#       "vendor_name": order_detail.get("vendorName"),
#       "invoice_number": order_detail.get("invoiceNumber"),
#       "customer_number": order_detail.get("customerNumber"),
#       "invoice_date": order_detail.get("invoiceDate"),
#       "created_date": order_detail.get("createdDate"),
#       "status": order_detail.get("status"),
#       "payment_account": order_detail.get("paymentAccount"),
#       "order_total": order_detail.get("orderTotal"),       # Total spend amount (includes taxes, delivery etc.)
#       "tax": order_detail.get("tax"),
#       "delivery_charges": order_detail.get("deliveryCharges"),
#       "other_charges": order_detail.get("otherCharges"),
#       "other_description": order_detail.get("otherDescription"),
#       "credit_amount": order_detail.get("creditAmount"),
#       "is_credit": order_detail.get("isCredit", False),    # True = credit memo, nets against spend
#       "input_tax_credits": order_detail.get("inputTaxCredits"),  # Canadian restaurants only
#       }


#   line_item_rows = []
#   for item in order_detail.get("lineItems", []):
#     is_category_level = item.get("vendorItemCode") is None and item.get("categoryId") is not None
#     line_item_rows.append({"order_id": order_id,
#                            "is_category_level": is_category_level,
#                            "category_id": item.get("categoryId"),
#                            "vendor_item_code": item.get("vendorItemCode"),
#                            "vendor_item_name": item.get("vendorItemName"),
#                            "company_concept_product_id": item.get("companyConceptProductId"),
#                            "packaging_id": item.get("packagingId"),
#                            "quantity": item.get("quantity"),
#                            "unit_price": item.get("unitPrice"),
#                            "line_price": item.get("linePrice"),
#                            })
#   return order_row, line_item_rows


# def extract_expenses(restaurant_unit_id, start_date: date, end_date: date, status: str = "CLOSED") -> tuple[pd.DataFrame, pd.DataFrame]:
#   """
#   Full pipeline: get orders in range, fetch detail for each order, build df.
#   N+1 call pattern: 1 (or more, if paginated) list calls + 1 detail call per order, all at 1 req/sec.
#   Budget ~1 sec per invoice for large date ranges consider chunking by month and running unattended, same as Toast labor pulls.

#   Args:
#     restaurant_unit_id: target restaurant's id
#     start_date: start date of the desired range
#     end_date: end date of the desired range
#     status: Order status, CLOSED by default to consider finalized orders
#   Returns
#     orders_df: DataFrame with all orders and their identifiers for fetching.
#     line_items_df: Dataframe with all items bought per order.
#   """
#   orders_summary = get_orders_list(restaurant_unit_id, start_date, end_date, status)

#   order_rows, line_item_rows = [], []
#   for idx, order_id in enumerate(orders_summary.get("orderId", [])):
#     detail = get_single_order_details(order_id, restaurant_unit_id)
#     o_row, li_rows = flatten_order_detail(detail)
#     order_rows.append(o_row)
#     line_item_rows.extend(li_rows)

#     if (idx + 1) % 25 == 0:
#       print(f"  ...{idx + 1}/{len(orders_summary)} invoices processed")

#   return pd.DataFrame(order_rows), pd.DataFrame(line_item_rows)