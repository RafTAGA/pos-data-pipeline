import requests # type: ignore
import json
import time
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import general_data_processing as processing # type: ignore

# Parameters of rate limiting (suggested by Toast's Chatbot)
SLEEP_BETWEEN_PAGES = 1.0 # secs between pages (within limit 5 req/seg)
SLEEP_BETWEEN_MONTHS = 7.0 # secs between months (backfill: 5-10 secs recommended by the chatbot)
PAGE_SIZE = 100 # max Toast allowed size
MAX_RETRIES_PER_PAGE = 3
HOUSTON_TZ = ZoneInfo("America/Chicago") 

##____________________________GENERAL API SUPPORTING FUNCTIONS___________________________________________________
def _get_access_token(toast_hostname:str, 
                      client_id: str, 
                      client_secret: str) -> tuple[str, str]:
    """
    Logins to Toast and asks for an Access Token
    Args:
      toast_hostname 
      client_id 
      client_secret: str

    Output:
      access_token
      expires_at_timestamp
    """
    url = f"https://{toast_hostname}/authentication/v1/authentication/login"
    body = {"clientId": client_id,
            "clientSecret": client_secret,
            "userAccessType": "TOAST_MACHINE_CLIENT"
            }

    # Troubleshooting
    # print(f"URL: {url}")
    # print(f"Client ID (repr): {repr(client_id)}  | length: {len(client_id)}")
    # print(f"Client Secret (repr, primeros/últimos 3 chars): "
    #       f"{repr(client_secret[:3])}...{repr(client_secret[-3:])} | length: {len(client_secret)}")
    # print(f"userAccessType (repr): {repr(body['userAccessType'])}")
    response = requests.post(url, json=body)

    if response.status_code != 200:
        # Safe to log status/body: Toast's error responses don't echo the secret back.
        print(f"LOGIN ERROR {response.status_code}: {response.text}")

    response.raise_for_status()
    data = response.json()

    token_block = data["token"]
    access_token = token_block["accessToken"]
    expires_in = token_block["expiresIn"]  # seconds
    expires_at = time.time() + expires_in

    print(f"Obtained Token expired in {expires_in} seconds ({expires_in/3600:.1f} hours).")
    return access_token, expires_at


def _ensure_valid_token(toast_hostname:str, 
                        client_id: str, 
                        client_secret: str, 
                        access_token, expires_at) -> tuple[str, str]:
    """
    Refreshes the token if it has less than 60 seconds of life remaining.
    Args:
      toast_hostname 
      client_id 
      client_secret
      access_token:  Output from _get_access_token()
      expires_at: Output from _get_access_token()

    Returns:
        access_token
        expires_at

    """
    if time.time() > (expires_at - 60):
        print("Token about to expire, requesting a new one...")
        return _get_access_token(toast_hostname=toast_hostname, 
                                 client_id=client_id, 
                                 client_secret=client_secret)
    
    return access_token, expires_at


#Transformación                                                                     | Quién la hace                             | Por qué se necesita
#datetime -> texto con formato 2024-05-01T00:00:00.000+0000                         | _format_toast_datetime() (usando strftime) |Toast no entiende objetos datetime de Python, necesita texto en un formato específico (ISO 8601)
#Texto con formato  2024-05-01T00:00:00.000+0000 → texto seguro para URL (%3A, %2B) | La librería requests automáticamente      |Las URLs no pueden contener ciertos caracteres especiales sin codificar
def _format_toast_datetime(dt):
    """
    Converts a NAIVE local (Houston) datetime into the UTC-based ISO 8601
    string Toast expects, e.g. 2026-06-01T05:00:00.000+0000.

    Args:
      dt: naive datetime representing Houston LOCAL wall-clock time
          (e.g. datetime(2026, 6, 1) meaning "June 1st, midnight, Houston time")

    Returns:
      String in Toast's required format, correctly offset to UTC — accounts
      for CDT (UTC-5, roughly Mar-Nov) vs CST (UTC-6, roughly Nov-Mar)
      automatically via zoneinfo, so no hardcoded offset needed regardless
      of which month is being extracted.
    """
    local_aware = dt.replace(tzinfo=HOUSTON_TZ)
    utc_dt = local_aware.astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def _daterange_days(start_dt, end_dt):
    """
    Yields each date (as a date object) from start_dt to end_dt, inclusive.
    Used to iterate refundBusinessDate one day at a time, since the /payments
    endpoint takes a single business date, not a start/end range like ordersBulk.

    Args:
      start_dt: datetime, first day (inclusive)
      end_dt: datetime, last day (inclusive)

    Returns:
      Generator of date objects.
    """
    current = start_dt.date()
    last = end_dt.date()
    while current <= last:
        yield current
        current += timedelta(days=1)


##____________________________API CATALOG EXTRACTION FUNCTIONS___________________________________________________
CATALOGS = [# (endpoint, output_filename, label)
           ("/config/v2/salesCategories", "catalog_sales_categories.json", "salesCategories"),
           ("/config/v2/revenueCenters", "catalog_revenue_centers.json", "revenueCenters"),
           ("/config/v2/diningOptions", "catalog_dining_options.json", "diningOptions"),
           ("/config/v2/tables", "catalog_tables.json", "tables"),
           ("/config/v2/menuItems", "catalog_menu_items.json", "menuItems"),
           #("/labor/v1/employees", "catalog_employees.json", "employees"),
           ("/labor/v1/jobs", "catalog_jobs.json", "jobs")
            ]

SLEEP_BETWEEN_CATALOGS = 2.0  # seconds between calls (catalogs are small, no bulk rate limit needed)


def fetch_catalog(toast_hostname: str, 
                  endpoint: str, 
                  access_token: str, 
                  restaurant_guid: str, 
                  label: str) -> list[dict]:
    """
    Calls a Configuration API or Labor API endpoint that returns a list of records.
    Args:
        toast_hostname
        endpoint: API path, e.g. "/config/v2/salesCategories"
        access_token: Bearer token
        restaurant_guid: Restaurant context header value
        label: Human-readable name for logs, e.g. "salesCategories"

    Returns:
        List of all records across all pages, or partial/empty list on failure.
    """
    base_url = f"https://{toast_hostname}{endpoint}"
    headers = {"Authorization": f"Bearer {access_token}",
               "Toast-Restaurant-External-ID": restaurant_guid}

    MAX_RETRIES = 3
    all_records = []
    page_token = None
    page_num = 1

    while True:
      params = {"pageToken": page_token} if page_token else {}
      retry_count = 0
      page_succeeded = False
      data = None
      response = None

      while retry_count < MAX_RETRIES:
        response = requests.get(base_url, 
                                headers=headers, 
                                params=params)

        if response.status_code == 429:
            print(f"  [{label}] Rate limited (page {page_num}). Waiting 15 seconds...")
            time.sleep(15)
            continue  # retry without incrementing retry_count

        if response.status_code == 200:
            data = response.json()
            page_succeeded = True
            break

        retry_count += 1
        print(f"  [{label}] ERROR {response.status_code} on page {page_num} "
              f"(attempt {retry_count}/{MAX_RETRIES}).")
        print(f"  URL: {response.url}")
        print(f"  Server response: {response.text}")

        if response.status_code >= 500 and retry_count < MAX_RETRIES:
            wait = 5 * retry_count
            print(f"  Retrying in {wait} seconds...")
            time.sleep(wait)
        else:
            break  # 4xx: no point retrying

      if not page_succeeded:
          print(f"  [{label}] Failed on page {page_num} after {retry_count} attempts. "
                f"Returning {len(all_records)} records collected so far.")
          return all_records

      all_records.extend(data)
      print(f"  [{label}] Page {page_num}: {len(data)} records "
            f"(total so far: {len(all_records)}).")

      page_token = response.headers.get("Toast-Next-Page-Token")
      if not page_token:
          break  # no more pages

      page_num += 1
      time.sleep(0.5)  # small pause between pages

    print(f"  [{label}] OK {len(all_records)} total records across {page_num} page(s).")
    return all_records


def run_catalog_extraction(toast_hostname:str, 
                           client_id:str, 
                           client_secret:str, 
                           output_dir: str, 
                           restaurant_guid: str)  -> None:
    """
    Extracts all catalogs needed to resolve GUIDs to human-readable names.
    Each catalog is saved as a JSON file in OUTPUT_DIR.

    Catalogs extracted:
        - salesCategories: resolves sales_category_guid
        - revenueCenters: resolves revenue_center_guid
        - diningOptions: resolves dining_option_guid
        - tables: resolves table_guid
        - menuItems: resolves item_guid (also includes sku, plu, calories, visibility)
        - employees: resolves server_guid
    """
    os.makedirs(output_dir, exist_ok=True)
    access_token, expires_at = _get_access_token(toast_hostname=toast_hostname, 
                                                 client_id=client_id, 
                                                 client_secret=client_secret)

    for endpoint, filename, label in CATALOGS:
        output_path = os.path.join(output_dir, filename)

        print(f"\nExtracting [{label}].........")

        access_token, expires_at = _ensure_valid_token(toast_hostname=toast_hostname, 
                                                       client_id=client_id, 
                                                       client_secret=client_secret, 
                                                       access_token=access_token, 
                                                       expires_at=expires_at)
        records = fetch_catalog(toast_hostname=toast_hostname, 
                                endpoint=endpoint, 
                                access_token=access_token, 
                                restaurant_guid=restaurant_guid, label=label)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"  [{label}] Saved: {len(records)} records: {output_path}")
        time.sleep(SLEEP_BETWEEN_CATALOGS)
    print("Catalog extraction complete!!!")


##____________________________API Item_GROUPS EXTRACTION FUNCTIONS___________________________________________________
ITEM_GROUP_GUIDS_LIST: list = []  # populate via df['item_group_guid'].dropna().unique().tolist()


def fetch_menu_groups_by_guid(toast_hostname: str, 
                              item_group_guids_list: list, 
                              access_token: str, 
                              restaurant_guid: str) -> tuple[list, list]:
    """
    Unlike the other catalogs, Toast has no "list all menu groups" endpoint.
    Each MenuGroup must be fetched individually via GET /menuGroups/{guid}.

    Args:
        item_group_guids_list: list of distinct item_group_guid values found in your order data
                               (get these from df['item_group_guid'].dropna().unique().tolist())
        access_token, restaurant_guid: same as other catalog calls

    Returns:
        List of dicts: [{"guid": "...", "name": "...", ...}, ...]
        Skips (and logs) any GUID that fails to resolve.
    """
    headers = {"Authorization": f"Bearer {access_token}",
               "Toast-Restaurant-External-ID": restaurant_guid
               }

    resolved_groups = []
    failed_guids = []

    print(f"\nResolving {len(item_group_guids_list)} menu group GUIDs individually "
          f"(no bulk-list endpoint exists for menuGroups)...")

    # LOOP through the GUIDs of MenuGrops
    for idx, guid in enumerate(item_group_guids_list, start=1):
        url = f"https://{toast_hostname}/config/v2/menuGroups/{guid}"
        response = requests.get(url, headers=headers)

        if response.status_code == 429:
            print(f"  [{idx}/{len(item_group_guids_list)}] Rate limited. Waiting 15 seconds...")
            time.sleep(15)
            response = requests.get(url, headers=headers)  # single retry after wait

        if response.status_code == 200:
            resolved_groups.append(response.json())
        else:
            print(f"  [{idx}/{len(item_group_guids_list)}] WARNING: failed to resolve {guid} "
                  f"(status {response.status_code})")
            failed_guids.append(guid)

        time.sleep(0.3)

    print(f"Resolved {len(resolved_groups)}/{len(item_group_guids_list)} menu groups. "
          f"{len(failed_guids)} failed.")

    return resolved_groups, failed_guids


def run_menu_groups_extraction(toast_hostname:str, 
                               client_id:str, 
                               client_secret:str, 
                               item_group_guids_list:list, 
                               output_dir: str, 
                               restaurant_guid: str) -> tuple[list, list]:
    """
    Resolves a list of item_group_guid values (e.g. from your orders DataFrame)
    to their MenuGroup names, and saves the result as catalog_menu_groups.json.

    This is separate from run_catalog_extraction() because menuGroups requires
    one API call per GUID (no bulk-list endpoint), unlike the other catalogs.

    Args:
        item_group_guids_list: list of distinct GUIDs to resolve.
                              Get these from your orders DataFrame, e.g.:
                              df['item_group_guid'].dropna().unique().tolist()

    Returns:
        List of dicts: [{"guid": "...", "name": "...", ...}, ...]
        Skips (and logs) any GUID that fails to resolve.
    """
    access_token, expires_at = _get_access_token(toast_hostname=toast_hostname, 
                                                 client_id=client_id, 
                                                 client_secret=client_secret)
    access_token, expires_at = _ensure_valid_token(toast_hostname=toast_hostname, 
                                                   client_id=client_id, 
                                                   client_secret=client_secret, 
                                                   access_token=access_token, 
                                                   expires_at=expires_at)
    resolved_groups, failed_guids = fetch_menu_groups_by_guid(toast_hostname=toast_hostname, 
                                                              item_group_guids_list=item_group_guids_list, 
                                                              access_token=access_token, 
                                                              restaurant_guid=restaurant_guid)

    output_path = os.path.join(output_dir, "catalog_menu_groups.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resolved_groups, f, ensure_ascii=False, indent=2)
    print(f"Saved: {len(resolved_groups)} menu groups → {output_path}")

    if failed_guids:
      failed_path = os.path.join(output_dir, "FAILED_menu_group_guids.json")
      with open(failed_path, "w", encoding="utf-8") as f:
          json.dump({"failed_guids": failed_guids}, f, indent=2)
      print(f"****** {len(failed_guids)} GUIDs failed to resolve. "
            f"Logged to {failed_path}")

    return resolved_groups, failed_guids


##____________________________API LABOR EXTRACTION FUNCTIONS__________________________________________________________________________________________________________________________________________________________

# Toast enforces a HARD LIMIT of 30 DAYS on the (startDate, endDate) and (modifiedStartDate, modifiedEndDate) interval for /labor/v1/timeEntries
# ERROR 400 confirmed it: {"message": "Cannot request time interval longer than 30 days"}.
# NOT the same as "one calendar month":
#      a 31-day month (Jan, Mar, May, Jul, Aug, Oct, Dec) will get rejected in a single request the whole thing in one call,
#      which is what the "one month max" guidance gets wrong in practice.
#
#Chunk in fixed MAX_CHUNK_DAYS windows (29 days, to stay safely under the 30-day cap with margin) instead of by calendar month.
MAX_CHUNK_DAYS = 29

#BASED ON https://www.youtube.com/watch?v=GWZf_B129zs
def _chunk_date_range(start_dt, 
                      end_dt, 
                      max_days:int=MAX_CHUNK_DAYS):
    """
    Yields (chunk_start, chunk_end) datetime pairs covering [start_dt, end_dt), where end_dt
    is treated as exclusive (matching Toast's endDate semantics: "before (exclusive) the
    endDate"). Each chunk spans at most max_days days (29), so every chunk safely respects Toast's
    30-day limit on /labor/v1/timeEntries date ranges.

    Args:
      start_dt: datetime, inclusive start of the overall range to extract.
      end_dt: datetime, exclusive end of the overall range to extract.
      max_days: int, maximum number of days per chunk (default 29, safely under Toast's 30-day cap).

    Returns:
      Yields (chunk_start, chunk_end) datetime tuples.
    """
    current = start_dt
    while current < end_dt:
        chunk_end = min(current + timedelta(days=max_days), end_dt)
        yield current, chunk_end
        current = chunk_end
###################### Concrete Example ######################################
#from datetime import datetime, timedelta
#start = datetime(2025, 1, 1)
#end   = datetime(2025, 3, 1)  # ~59 days

#for chunk_start, chunk_end in _chunk_date_range(start, end):
#    print(chunk_start.date(), "->", chunk_end.date())
#Output:
#     2025-01-01 -> 2025-01-30   # chunk 1: 29 days
#     2025-01-30 -> 2025-03-01   # chunk 2: remaining 30 days (under the cap)

#Loop iteration 1 → function runs until yield, hands back (Jan 1, Jan 30), then freezes
#   print runs with those values
#Loop iteration 2 → function unfreezes, runs current = chunk_end (now Jan 30), loops back to while, yields (Jan 30, Mar 1), freezes again
#   print runs with those values
#Loop iteration 3 → function unfreezes, current = Mar 1, while current < end_dt is False, function ends, loop stops
#   print runs with those values
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


# Extract Time Entries within a Date Range
# IMPORTANT: unlike /orders/v2/ordersBulk, the Labor API's /labor/v1/timeEntries endpoint does NOT support page/pageSize pagination.
# A single GET for a date range returns the full array of matching TimeEntry objects, so there is no page loop here.
#       Valid Toast query combos for this endpoint: (startDate & endDate) OR (modifiedStartDate & modifiedEndDate) OR businessDate (a single date, not a range) OR one/more timeEntryIds.
#       We use startDate/endDate, chunked into <=29 day windows (see _chunk_date_range above).
#       Also note: startDate/endDate filter on each TimeEntry's inDate (clock-in time), NOT on businessDate.
#       Daily totals below are grouped by businessDate (which accounts for the restaurant's closeoutHour),
#       so a shift that clocks in right at a chunk boundary could land in a different businessDate than the chunk you fetched it in - that's expected and resolves itself once the adjacent chunk has also been pulled.
def _fetch_time_entries_for_range(start_date: str, 
                                  end_date: str, 
                                  access_token: str, 
                                  restaurant_guid: str, 
                                  toast_hostname: str) -> list[dict]:
    """
    Extracts ALL TimeEntry records within a date range.

    Asserts the requested interval is <= 30 days before ever calling the
    API (Toast's actual documented/enforced limit for /labor/v1/timeEntries), so a bad date
    range fails fast locally instead of burning a request on a guaranteed 400.

    Deals with transient errors via retries; if a request ultimately fails it raises so the
    caller can decide whether to stop or skip the chunk.

    Args:
      start_date: string, Toast format (ISO 8601, ej. "2025-01-01T00:00:00.000+0000")
      end_date: string, Toast format (ISO 8601, ej. "2025-01-01T00:00:00.000+0000")
      access_token: Access token obtained from _get_access_token().
      restaurant_guid: string, restaurantGuid provided by user.

    Returns:
      time_entries: list, TimeEntry dicts (each one has regularHours, overtimeHours, businessDate, employeeReference, jobReference, inDate, outDate, breaks, etc.)
    """
    start_dt_check = datetime.strptime(start_date[:19], "%Y-%m-%dT%H:%M:%S")
    end_dt_check = datetime.strptime(end_date[:19], "%Y-%m-%dT%H:%M:%S")

    if (end_dt_check - start_dt_check) > timedelta(days=30):
        raise ValueError(
            f"Date range {start_date} -> {end_date} exceeds Toast's 30-day limit for "
            f"/labor/v1/timeEntries (startDate/endDate). Split it into smaller chunks."
        )

    url = f"https://{toast_hostname}/labor/v1/timeEntries"

    headers = {"Authorization": f"Bearer {access_token}",
               "Toast-Restaurant-External-ID": restaurant_guid}

    params = {"startDate": start_date,
              "endDate": end_date,
              "includeMissedBreaks": "true"}

    MAX_RETRIES = 3
    retry_count = 0
    time_entries = None

    while retry_count < MAX_RETRIES:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 429:  # HTTP 429 Too Many Requests
            print("  Too many requests. Wait 15 segundos...")
            time.sleep(15)
            continue  # retry without counting against retry_count

        if response.status_code == 200:  # Success
            time_entries = response.json()
            break

        # Handling Errors (400, 500, etc.)
        retry_count += 1
        print(f"  ERROR {response.status_code} (attempt {retry_count}/{MAX_RETRIES}).")
        print(f"  URL completa: {response.url}")
        print(f"  Respuesta del servidor: {response.text}")

        #Server errors 500 (Toast errors that usually solve with new attempts)
        if response.status_code >= 500 and retry_count < MAX_RETRIES:
            wait = 5 * retry_count  # backoff progresivo: 5s, 10s, 15s
            print(f"  Reintentando en {wait} segundos...")
            time.sleep(wait)

        #User call errors that only get solved with code.
        elif response.status_code < 500:
            response.raise_for_status()  # user/request error, not worth retrying blindly
            #NO PAGE FUNCTIONALITY SO NO NEED TO REPLICATE ORDER SCRAPING CODE HERE.

    if time_entries is None:
        # Exhausted retries on 5xx errors
        response.raise_for_status()

    return time_entries


def run_labor_extraction(toast_hostname:str,
                         client_id:str,
                         client_secret:str,
                         restaurant_guid:str,
                         start_date: tuple,
                         end_date: tuple,
                         output_dir: str,) -> None:
    """
    Extracts time entries from Toast between (start_date, end_date) inclusive,
    chunked into <=29-day windows (see _chunk_date_range).

    Args:
      start_date: tuple (year, month, day), inclusive start
      end_date: tuple (year, month, day), inclusive end

    Returns:
      None, saves JSON files of all pages within the date range.
    """
    #Get access token and its expiration time remaining
    os.makedirs(output_dir, exist_ok=True)
    access_token, expires_at = _get_access_token(toast_hostname=toast_hostname,
                                                 client_id=client_id,
                                                 client_secret=client_secret)

    #Overall range to cover: exact requested start day through the day AFTER the requested end day (exclusive).
    overall_start = datetime(*start_date)
    overall_end = datetime(*end_date) + timedelta(days=1)

    #30 day chunks limit
    for chunk_start, chunk_end in _chunk_date_range(overall_start, overall_end):
        chunk_label = f"{chunk_start:%Y%m%d}_{(chunk_end - timedelta(days=1)):%Y%m%d}"
        raw_output_path = os.path.join(output_dir, f"time_entries_{chunk_label}.json")

        print(f"\n Extracting [{chunk_label}]...")

        if os.path.exists(raw_output_path):
            print(f"[{chunk_label}] Raw file already exists, loading from disk instead of re-fetching.")
            with open(raw_output_path, "r", encoding="utf-8") as f:
                time_entries = json.load(f)
        else:
            # Refresh token if already expired....
            access_token, expires_at = _ensure_valid_token(toast_hostname=toast_hostname, 
                                                           client_id=client_id, 
                                                           client_secret=client_secret, 
                                                           access_token=access_token, 
                                                           expires_at=expires_at)
            start_str = _format_toast_datetime(chunk_start)
            end_str = _format_toast_datetime(chunk_end)

            #STOP if error is found
            try:
                time_entries = _fetch_time_entries_for_range(start_date=start_str,
                                                             end_date=end_str,
                                                             access_token=access_token,
                                                             restaurant_guid=restaurant_guid,
                                                             toast_hostname=toast_hostname,
                                                             )
            except requests.exceptions.HTTPError as e:
                print(f"[{chunk_label}] ERROR: {e}")
                print("Stopping extraction due to ERROR. Please review the ERROR.")
                break

            # Save raw JSON
            with open(raw_output_path, "w", encoding="utf-8") as f:
                json.dump(time_entries, f, ensure_ascii=False, indent=2)

            print(f"[{chunk_label}] Saved: {len(time_entries)} time entries saved in: {raw_output_path}")


##____________________________API ORDER EXTRACTION FUNCTIONS__________________________________________________________________________________________________________________________________________________________
#Extract Data within a Range of Dates (1 month maximum as recommended by Toast Chatbot)
def fetch_orders_for_range(toast_hostname:str, 
                           start_date:str, 
                           end_date:str, 
                           access_token:str, 
                           restaurant_guid:str) -> tuple[list, list]:
    """
    Extracts ALL orders within a date range (1 month max suggested)

    Deal corrupt enties by skipping it and registering it to avoid loosing progress and continue
    getting orders.

    Args:
    start_date: strings in Toast format (ISO 8601, ej. "2025-01-01T00:00:00.000+0000")
    end_date: strings in Toast format (ISO 8601, ej. "2025-01-01T00:00:00.000+0000")
    access_token: Access codes provided by user.
    restaurant_guid: Access codes provided by user.

    Returns:
    all_orders: list of succesfull order
    failed_pages: List of failed pages with 100 orders that were currupted or unaccessible and therefore excluded.
    """
    
    all_orders = []
    failed_pages = []
    page = 1
    

    #url where orders are located, provided by the Toast Chatbot
    #Chatbot says ulr should be:
    #https://[hostname]/orders/v2/ordersBulk?startDate=2026-06-16T00%3A00%3A00.000%2B0000&endDate=2026-06-17T00%3A00%3A00.000%2B0000&pageSize=100&page=1.
    url = f"https://{toast_hostname}/orders/v2/ordersBulk"

    headers = {"Authorization": f"Bearer {access_token}",
               "Toast-Restaurant-External-ID": restaurant_guid}

    while True:
      params = {"startDate": start_date,
              "endDate": end_date,
              "page": page,
              "pageSize": PAGE_SIZE}

      retry_count = 0
      page_succeeded = False
      orders = None

      #Try 3 time fecthing a page.
      while retry_count < MAX_RETRIES_PER_PAGE:
        response = requests.get(url, headers=headers, params=params)
        #Retry with delay to not saturate the server

        #Retry with delay to not saturate the server
        if response.status_code == 429: #HTTP 429 Too Many Requests.
          print(f"  Too many requests in page:{page}. Wait 15 segundos...")
          time.sleep(15)
          continue  # retry

        if response.status_code == 200: #Success
          orders = response.json()
          page_succeeded = True
          break

        # Handling Errors (400, 500, etc.)
        retry_count += 1
        print(f"  ERROR {response.status_code} in page {page} ")
        print(f"(attempt {retry_count}/{MAX_RETRIES_PER_PAGE}).")
        print(f"  URL completa: {response.url}")
        print(f"  Respuesta del servidor: {response.text}")

        #Server errors 500 (Toast errors that usually solve with new attempts)
        if response.status_code >= 500 and retry_count < MAX_RETRIES_PER_PAGE:
          wait = 5 * retry_count  # backoff progresivo: 5s, 10s, 15s
          print(f"  Reintentando en {wait} segundos...")
          time.sleep(wait)

        #USer call errors that only get solved with code.
        elif response.status_code < 500:
                # skip the page and since page_succeeded = False never changed:
                # Report page as failed.
                break

        #If page failed
      if not page_succeeded:
        print(f" PAGE {page} FAILED AFTER {retry_count} ATTEMPTS!!!!!!"
             f"\n\t SKIPING THIS PAGE................................")
        failed_pages.append(page)
        page += 1 #NEXT PAGE
        time.sleep(SLEEP_BETWEEN_PAGES) #Wait some time before the next request
        continue

        #If page empty, meaning end of records
      if not orders:  # array vacío => fin de la paginación
        print(f"PAGE {page}: EMPTY, END OF EXTRACTION.")
        break

      #Pages done, go to next stage (month)
      print(f"PAGE {page}: CONTAINS {len(orders)} ORDERS COLLECTED.")
      all_orders.extend(orders)

      #Next page and wait before next request.
      page += 1
      time.sleep(SLEEP_BETWEEN_PAGES)

    return all_orders, failed_pages


def run_order_extraction(toast_hostname:str,
                         restaurant_guid:str,
                         client_id:str,
                         client_secret:str,
                         start_date:tuple,
                         end_date:tuple,
                         output_dir:str) -> None:
  """
  Extract orders from toast between date ranges.
  Args:
    start_date: tuple (year, month, day), inclusive start
    end_date: tuple (year, month, day), inclusive end

  returns:
    None, saves JSON files of all pages within the date range.

  """
  SLEEP_BETWEEN_MONTHS = 7.0 # secs between months (backfill: 5-10 secs recommended by the chatbot)
  os.makedirs(output_dir, exist_ok=True)
  #Get access token and its expiration time remaining
  access_token, expires_at = _get_access_token(toast_hostname=toast_hostname,
                                               client_id=client_id,
                                               client_secret=client_secret)

  #For each calendar month touched by [start_date, end_date], clipped to the exact days requested
  for year, month, day_start, day_end, is_full_month in processing.month_chunks(date(*start_date), date(*end_date)):

      #Build a label and the name of the JSON file. Whole-month requests (backfills) keep the
      #original "{year}_{month:02d}" naming/skip-caching; partial ranges (weekly incremental runs)
      #get a distinct label so they don't collide with -- or get skipped by -- a whole-month file.
      label = f"{year}_{month:02d}" if is_full_month else f"{year}_{month:02d}_{day_start:02d}to{day_end:02d}"
      output_path = os.path.join(output_dir, f"orders_{label}.json")

      # If documents already exist, skip, to avoid starting from start in case of interruption.
      if os.path.exists(output_path):
        print(f"[{label}] Already extracted, skipping.")
        continue

      print(f"\n Exctracting [{label}]...")

      # Refresh token if already expired....
      access_token, expires_at = _ensure_valid_token(toast_hostname=toast_hostname,
                                                     client_id=client_id,
                                                     client_secret=client_secret,
                                                     access_token=access_token,
                                                     expires_at=expires_at)

      # Get exact day range for this segment
      start_dt = datetime(year, month, day_start)
      end_dt = datetime(year, month, day_end) + timedelta(days=1) - timedelta(seconds=1)
      #Format date ranges
      start_str = _format_toast_datetime(start_dt)
      end_str = _format_toast_datetime(end_dt)

      #STOP if error is found
      try:
        orders, failed_pages = fetch_orders_for_range(toast_hostname=toast_hostname,
                                                      start_date=start_str,
                                                      end_date=end_str,
                                                      access_token=access_token,
                                                      restaurant_guid=restaurant_guid)
      except requests.exceptions.HTTPError as e:
        print(f"[{label}] ERROR: {e}")
        print("Stopping extraction due to ERROR. Please review the ERROR.")
        break

      # Save raw JSON
      with open(output_path, "w", encoding="utf-8") as f:
          json.dump(orders, f, ensure_ascii=False, indent=2)

      print(f"[{label}] Saved: {len(orders)} orders saved in: {output_path}")

      if failed_pages:
          print(f"[{label}] WARNING: pages {failed_pages} failed to be extracted."
                f"Some orders may be missing for the range.")
          failed_log_path = os.path.join(output_dir, f"FAILED_PAGES_{label}.json")
          with open(failed_log_path, "w", encoding="utf-8") as f:
              json.dump({
                  "range": label,
                  "failed_pages": failed_pages,
                  "start_date": start_str,
                  "end_date": end_str
              }, f, indent=2)

      time.sleep(SLEEP_BETWEEN_MONTHS)

  print("\n SCRAPPING COMPLETE or STOPPED BY ERROR, CONFIRM WITH LOGS!")


##____________________________API REFUND EXTRACTION FUNCTIONS__________________________________________________________________________________________________________________________________________________________
def fetch_refunded_payment_guids(toast_hostname:str, 
                                 business_date_str:str, 
                                 access_token:str, 
                                 restaurant_guid:str) -> list[str]:
    """
    Gets the list of payment GUIDs refunded on a given business date.
    GET /payments?refundBusinessDate=yyyyMMdd returns GUIDs only — no refund
    detail. Call fetch_payment_detail() per GUID to get refundAmount/tipRefundAmount.

    Args:
      business_date_str: string, "yyyyMMdd" e.g. "20250115"
      access_token: string
      restaurant_guid: string

    Returns:
      List of payment GUID strings (empty list if none refunded that day).
    """
    url = f"https://{toast_hostname}/orders/v2/payments"
    headers = {"Authorization": f"Bearer {access_token}",
               "Toast-Restaurant-External-ID": restaurant_guid}
    params = {"refundBusinessDate": business_date_str}

    MAX_RETRIES = 3
    retry_count = 0
    while retry_count < MAX_RETRIES:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 429:
            print(f"  Too many requests fetching GUIDs for {business_date_str}. Waiting 15s...")
            time.sleep(15)
            continue

        if response.status_code == 200:
            return response.json() or []

        retry_count += 1
        print(f"  ERROR {response.status_code} fetching GUIDs for {business_date_str} "
              f"(attempt {retry_count}/{MAX_RETRIES}). Response: {response.text}")
        if response.status_code >= 500 and retry_count < MAX_RETRIES:
            time.sleep(5 * retry_count)
        elif response.status_code < 500:
            break

    print(f"  FAILED to get refunded payment GUIDs for {business_date_str}.")
    return []


def fetch_payment_detail(toast_hostname:str, 
                         payment_guid:str, 
                         access_token, 
                         restaurant_guid) -> dict:
    """
    Gets full payment details for one payment GUID, including the nested
    Refund object (refundAmount, tipRefundAmount, refundDate, refundBusinessDate).

    Args:
      payment_guid: string
      access_token: string
      restaurant_guid: string

    Returns:
      Dict of the payment object, or None if the request failed after retries.
    """
    url = f"https://{toast_hostname}/orders/v2/payments/{payment_guid}"
    headers = {"Authorization": f"Bearer {access_token}",
               "Toast-Restaurant-External-ID": restaurant_guid}

    MAX_RETRIES = 3
    retry_count = 0
    while retry_count < MAX_RETRIES:
        response = requests.get(url, headers=headers)

        if response.status_code == 429:
            print(f"  Too many requests fetching payment {payment_guid}. Waiting 15s...")
            time.sleep(15)
            continue

        if response.status_code == 200:
            return response.json()

        retry_count += 1
        print(f"  ERROR {response.status_code} fetching payment {payment_guid} "
              f"(attempt {retry_count}/{MAX_RETRIES}). Response: {response.text}")
        if response.status_code >= 500 and retry_count < MAX_RETRIES:
            time.sleep(5 * retry_count)
        elif response.status_code < 500:
            break

    print(f"  FAILED to fetch payment detail for {payment_guid}.")
    return None


def fetch_refunds_for_range(toast_hostname:str, 
                            start_dt:str, 
                            end_dt:str, 
                            access_token:str, 
                            restaurant_guid:str) -> list[dict]:
    """
    Fetches all refunded payments (full detail) for every business day in the
    given range. Iterates day-by-day (refundBusinessDate is single-day only),
    and for each refunded payment GUID found, fetches its full detail.

    Args:
      start_dt: datetime, first day of the range
      end_dt: datetime, last day of the range
      access_token: string
      restaurant_guid: string

    Returns:
      List of payment detail dicts (each includes the nested Refund object).
    """
    all_payments = []

    for day in _daterange_days(start_dt, end_dt):
        business_date_str = day.strftime("%Y%m%d")
        guids = fetch_refunded_payment_guids(toast_hostname=toast_hostname, 
                                             business_date_str=business_date_str, 
                                             access_token=access_token, 
                                             restaurant_guid=restaurant_guid)

        if not guids:
            continue

        print(f"  [{business_date_str}] {len(guids)} refunded payment(s) found.")

        for guid in guids:
            payment = fetch_payment_detail(toast_hostname=toast_hostname, 
                                           payment_guid=guid, 
                                           access_token=access_token, 
                                           restaurant_guid=restaurant_guid)
            if payment is not None:
                all_payments.append(payment)
            time.sleep(SLEEP_BETWEEN_PAGES)  # reuse existing rate-limit constant

    return all_payments


def run_refund_extraction(toast_hostname:str,
                          restaurant_guid:str,
                          client_id:str,
                          client_secret:str,
                          start_date:tuple,
                          end_date:tuple,
                          output_dir:str) -> None:
    """
    Extracts refunded payments from Toast between date ranges, one calendar month at a time (clipped to the exact days requested), 
    saving each segment's refunds to its own JSON file. Mirrors run_order_extraction's structure (token refresh, skip-if-exists, 
    error handling), adapted for day-by-day /payments pattern.

    Args:
      start_date: tuple (year, month, day), inclusive start
      end_date: tuple (year, month, day), inclusive end

    Returns:
      None, saves one JSON file per calendar-month segment of refunded payment details.
    """
    os.makedirs(output_dir, exist_ok=True)
    access_token, expires_at = _get_access_token(toast_hostname=toast_hostname,
                                                 client_id=client_id,
                                                 client_secret=client_secret)

    for year, month, day_start, day_end, is_full_month in processing.month_chunks(date(*start_date), date(*end_date)):
        label = f"{year}_{month:02d}" if is_full_month else f"{year}_{month:02d}_{day_start:02d}to{day_end:02d}"
        output_path = os.path.join(output_dir, f"refunds_{label}.json")

        if os.path.exists(output_path):
            print(f"[{label}] Already extracted, skipping.")
            continue

        print(f"\nExtracting refunds for [{label}]...")
        access_token, expires_at = _ensure_valid_token(toast_hostname=toast_hostname,
                                                       client_id=client_id,
                                                       client_secret=client_secret,
                                                       access_token=access_token,
                                                       expires_at=expires_at)
        start_dt = datetime(year, month, day_start)
        end_dt = datetime(year, month, day_end) + timedelta(days=1) - timedelta(seconds=1)

        try:
            payments = fetch_refunds_for_range(toast_hostname=toast_hostname,
                                               start_dt=start_dt,
                                               end_dt=end_dt,
                                               access_token=access_token,
                                               restaurant_guid=restaurant_guid)

        except requests.exceptions.HTTPError as e:
            print(f"[{label}] ERROR: {e}")
            print("Stopping extraction due to ERROR. Please review the ERROR.")
            break

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payments, f, ensure_ascii=False, indent=2)

        print(f"[{label}] Saved: {len(payments)} refunded payments to: {output_path}")
        time.sleep(SLEEP_BETWEEN_MONTHS)

    print("\nREFUND EXTRACTION COMPLETE or STOPPED BY ERROR, CONFIRM WITH LOGS!")