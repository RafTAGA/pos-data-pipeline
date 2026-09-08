--______________________________ MarginEdge Purchaise Orders _____________________________________________________________________
--CREATE MarginEdge marginedge_orders
CREATE TABLE marginedge_orders (
    order_id             BIGINT PRIMARY KEY,
    vendor_id            BIGINT,
    vendor_name          TEXT,
    invoice_number       TEXT,
    customer_number      TEXT,
    invoice_date         DATE,
    created_date         DATE,
    status               TEXT,
    payment_account      TEXT,
    order_total          NUMERIC(12,2),
    tax                  NUMERIC(12,2),
    delivery_charges     NUMERIC(12,2),
    other_charges        NUMERIC(12,2),
    other_description    TEXT,
    credit_amount        NUMERIC(12,2),
    is_credit            BOOLEAN,
    input_tax_credits    NUMERIC(12,2),
    yyyyMMdd              DATE
);


--CREATE MarginEdge marginedge_line_items
CREATE TABLE marginedge_line_items (
    order_id                    BIGINT NOT NULL,
    line_item_index             INTEGER NOT NULL,
    is_category_level           BOOLEAN,
    category_id                 INTEGER,
    vendor_item_code            TEXT,
    vendor_item_name            TEXT,
    company_concept_product_id  BIGINT,
    packaging_id                INTEGER,
    quantity                    NUMERIC(12,4),
    unit_price                  NUMERIC(12,4),
    line_price                  NUMERIC(12,2),
    PRIMARY KEY (order_id, line_item_index)
);

--______________________________ MarginEdge CATALOGS _____________________________________________________________________
--CREATE MarginEdge catalog_vendors
CREATE TABLE catalog_vendors (
    vendor_id         BIGINT,
    central_vendor_id BIGINT,
    vendor_name       TEXT,
    vendor_accounts   JSONB
);


--CREATE MarginEdge catalog_purchase_categories
CREATE TABLE catalog_purchase_categories (
    category_id      INTEGER,
    category_name    TEXT,
    category_type    TEXT,
    accounting_code  TEXT
);

--______________________________ Toast CATALOGS _____________________________________________________________________
--CREATE Toast catalog_revenue_centers
CREATE TABLE catalog_revenue_centers (
    revenue_center_guid  TEXT,
    revenue_center       TEXT
);


--CREATE Toast catalog_menu_items
CREATE TABLE catalog_menu_items (
    item_guid  TEXT,
    item       TEXT
);


--CREATE Toast catalog_sales_categories
CREATE TABLE catalog_sales_categories (
    sales_category_guid  TEXT,
    category              TEXT
);


--CREATE Toast catalog_tables
CREATE TABLE catalog_tables (
    table_guid    TEXT,
    table_number  TEXT
);


--CREATE Toast catalog_dining_options
CREATE TABLE catalog_dining_options (
    dining_option_guid  TEXT,
    dining_option       TEXT
);


--______________________________ Toast TABLES _____________________________________________________________________
--CREATE Toast refunds_daily_summary
CREATE TABLE refunds_daily_summary (
    guid              TEXT PRIMARY KEY,
    yyyyMMdd          DATE,
    refund_amount     NUMERIC(12,2),
    tip_refund_amount NUMERIC(12,2)
);


--CREATE Toast labor_time_entries
CREATE TABLE labor_time_entries (
    time_entry_guid  TEXT PRIMARY KEY,
    employee_guid  TEXT, 
    in_date        TIMESTAMPTZ,
    out_date       TIMESTAMPTZ,
    regular_hours  NUMERIC(6,2),
    overtime_hours NUMERIC(6,2),
    total_hours    NUMERIC(6,2),
    hourly_wage    NUMERIC(6,2),
    regular_pay    NUMERIC(6,2),
    overtime_pay   NUMERIC(6,2),
    total_pay      NUMERIC(6,2),
    deleted        BOOLEAN,
    yyyyMMdd       DATE,
    title          TEXT
);


--CREATE Toast item_sales
CREATE TABLE item_sales (
    check_guid          TEXT,
    selection_guid      TEXT PRIMARY KEY,
    item_display_name   TEXT,
    item_guid           TEXT,
    sales_category_guid TEXT,
    item_voided         BOOLEAN,
    quantity            NUMERIC(6,2),
    price               NUMERIC(10,2),
    pre_discount_price  NUMERIC(10,2),
    unit_price          NUMERIC(10,2),
    total_discount      NUMERIC(10,2),
    unit_discount        NUMERIC(10,2)
);


--CREATE Toast toast_order_checks
CREATE TABLE toast_order_checks (
    order_guid            TEXT,
    order_voided          BOOLEAN,
    order_deleted         BOOLEAN,
    order_excess_food     BOOLEAN,
    number_of_guests      INTEGER,
    check_guid            TEXT PRIMARY KEY,
    check_voided          BOOLEAN,
    check_deleted         BOOLEAN,
    check_net_amount      NUMERIC(12,2),
    yyyyMMdd              DATE,
    hour                  SMALLINT,
    paid_hour             SMALLINT,
    sitting_duration_secs INTEGER,
    dining_option_guid    TEXT,
    revenue_center_guid   TEXT,
    table_guid            TEXT
);


--______________________________ Open Meteo _____________________________________________________________________
--CREATE Weather weather_daily_summary
CREATE TABLE weather_daily_summary (
    yyyyMMdd                  DATE PRIMARY KEY,
    temperature_2m_max        DOUBLE PRECISION,
    temperature_2m_min        DOUBLE PRECISION,
    temperature_2m_mean       DOUBLE PRECISION,
    apparent_temperature_max  DOUBLE PRECISION,
    apparent_temperature_min  DOUBLE PRECISION,
    precipitation_sum         DOUBLE PRECISION,
    rain_sum                  DOUBLE PRECISION,
    precipitation_hours       DOUBLE PRECISION,
    snowfall_sum               DOUBLE PRECISION,
    windspeed_10m_max          DOUBLE PRECISION,
    windgusts_10m_max          DOUBLE PRECISION,
    relative_humidity_2m_mean  SMALLINT,
    cloudcover_mean             SMALLINT,
    shortwave_radiation_sum      DOUBLE PRECISION
);


--______________________________ Toast VIEWS _____________________________________________________________________
-- Recreates the daily_sales / hourly_sales summaries,
-- (previously only produced as standalone CSVs by json_processing_toast_order.py's DAILY/HOURLY SUMMARY EXCLUSIVE FUNCTIONS) 

-- 
-- 1) order-level exclusions: order_voided, order_deleted, order_excess_food

-- 2) check-level exclusions: check_voided, check_deleted (only affects net_sales;
--      an order with all its checks voided still counts toward number_of_orders /
--      number_of_guests, matching parse_orders_json_daily_summary's behavior)
-- 3) unpaid orders are already excluded upstream, at parse_orders_json() parse time

-- CREATE Toast daily_sales_summary
CREATE OR REPLACE VIEW daily_sales_summary AS
--TEMPORARY TABLE of Valid orders
WITH valid_orders AS (
                    --order unique constant columns are order_guid, yyyyMMdd, number_of_guests
                    --Doing this keeps all three unique combinations and removing duplicates generated by different checks' data
                    SELECT DISTINCT order_guid, yyyyMMdd, number_of_guests
                    FROM toast_order_checks
                    WHERE NOT order_voided AND NOT order_deleted AND NOT order_excess_food
                    ),
--TEMPORARY TABLE of Valid checks
valid_check_sales AS (
                    -- SUM check_net_amount of different checks with the same order guid, remider that the feature used to group has to also be SELECTED
                    SELECT order_guid, SUM(check_net_amount) AS order_net_sales
                    FROM toast_order_checks
                    --UNECESSARY BUT COMPUTES FASTER
                    WHERE NOT order_voided AND NOT order_deleted AND NOT order_excess_food
                    AND NOT check_voided AND NOT check_deleted
                    GROUP BY order_guid
                    ),
--TEMPORARY TABLE made by JOINING  valid_orders and valid_check_sales
daily_gross AS (
                SELECT
                    vo.yyyyMMdd,
                    SUM(COALESCE(vcs.order_net_sales, 0)) AS gross_net_sales,
                    COUNT(DISTINCT vo.order_guid) AS number_of_orders,
                    SUM(vo.number_of_guests) AS number_of_guests
                FROM valid_orders AS vo
                LEFT JOIN valid_check_sales AS vcs ON vcs.order_guid = vo.order_guid
                GROUP BY vo.yyyyMMdd
                ),
--TEMPORARY TABLE made by JOINING  valid_orders and valid_check_sales
daily_refunds AS (
                SELECT 
                    yyyyMMdd, SUM(refund_amount) AS refund_amount, 
                    SUM(tip_refund_amount) AS tip_refund_amount
                FROM refunds_daily_summary
                GROUP BY yyyyMMdd
                )
SELECT
    dg.yyyyMMdd,
    --COALESCE(dr.refund_amount, 0) uses dr.refund_amount if it has a real value, otherwise uses 0. It exists specifically to handle the LEFT JOIN's Nulls
    dg.gross_net_sales - COALESCE(dr.refund_amount, 0) - COALESCE(dr.tip_refund_amount, 0) AS net_sales,
    dg.number_of_orders,
    dg.number_of_guests
FROM daily_gross AS dg
LEFT JOIN daily_refunds AS dr ON dr.yyyyMMdd = dg.yyyyMMdd;


-- CREATE Toast hourly_sales_view
-- Uses paid_hour (derived from paidDate).
-- No refunds subtraction as these cannot be backtracked that easily with standard API access.
CREATE OR REPLACE VIEW hourly_sales_view AS
--TEMPORARY TABLE of Valid orders
WITH valid_orders AS (
    SELECT DISTINCT order_guid, yyyyMMdd, paid_hour, number_of_guests
    FROM toast_order_checks
    WHERE NOT order_voided AND NOT order_deleted AND NOT order_excess_food
),
--TEMPORARY TABLE of Valid orders
valid_check_sales AS (
    SELECT order_guid, SUM(check_net_amount) AS order_net_sales
    FROM toast_order_checks
    WHERE NOT order_voided AND NOT order_deleted AND NOT order_excess_food
      AND NOT check_voided AND NOT check_deleted
    GROUP BY order_guid
)
--MAIN QUERY
SELECT
    vo.yyyyMMdd,
    vo.paid_hour AS hour,
    --CASE WHEN WE HAVE 12 and 24, turn them into 12
    CASE WHEN vo.paid_hour % 12 = 0 THEN 12 ELSE vo.paid_hour % 12 END
    --' ' is just a string literal, a single space character wrapped in quotes — and || glues it in between the two other pieces.
        || ' ' || CASE WHEN vo.paid_hour < 12 THEN 'AM' ELSE 'PM' END AS hour_label,
    SUM(COALESCE(vcs.order_net_sales, 0)) AS net_sales,
    COUNT(DISTINCT vo.order_guid) AS number_of_orders,
    SUM(vo.number_of_guests) AS number_of_guests
FROM valid_orders AS vo
LEFT JOIN valid_check_sales AS vcs ON vcs.order_guid = vo.order_guid
GROUP BY vo.yyyyMMdd, vo.paid_hour;


-- CREATE Toast monthly_sales_summary
-- Rolls daily_sales_summary up to month grain, plus month-over-month sales growth %.
CREATE OR REPLACE VIEW monthly_sales_summary AS
WITH monthly AS ( --Make a view grouped by month
    SELECT
        date_trunc('month', yyyyMMdd)::date AS year_month,
        SUM(net_sales)         AS net_sales,
        SUM(number_of_orders)  AS number_of_orders,
        SUM(number_of_guests)  AS number_of_guests
    FROM daily_sales_summary
    GROUP BY date_trunc('month', yyyyMMdd)
)
SELECT --Create the new table from the monthly view's columns.
    net_sales,
    number_of_orders,
    number_of_guests,

    --Use the previous row on the year_month and store the value as prev Net sales
    LAG(net_sales) OVER (ORDER BY year_month) AS "prev Net sales",
    -- Create the sales growth using the (100 * (current-prev)/prev) making NULL if prev does not exist (previous is first month).
    100.0 * (net_sales - LAG(net_sales) OVER (ORDER BY year_month))
        / NULLIF(LAG(net_sales) OVER (ORDER BY year_month), 0) AS "sales growth",
    year_month AS yyyyMMdd
FROM monthly
ORDER BY year_month;