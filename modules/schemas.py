import pandas as pd

##___________________________ MarginEdge ______________________________
MARGINEDGE_ORDERS_SCHEMA = {
    "order_id": "int64",
    "vendor_id": "int64",
    "vendor_name": "string",
    "invoice_number": "string",
    "customer_number": "string",
    "invoice_date": "date",
    "created_date": "date",
    "status": "string",
    "payment_account": "string",
    "order_total": "float64",
    "tax": "float64",
    "delivery_charges": "float64",
    "other_charges": "float64",
    "other_description": "string",
    "credit_amount": "float64",
    "is_credit": "bool",
    "input_tax_credits": "float64",
    "yyyymmdd": "date",
}

MARGINEDGE_LINE_ITEMS_SCHEMA = {
    "order_id": "int64",
    "line_item_index": "int64",
    "is_category_level": "bool",
    "category_id": "int64",   
    "vendor_item_code": "string",
    "vendor_item_name": "string",
    "company_concept_product_id": "int64",
    "packaging_id": "int64",
    "quantity": "float64",
    "unit_price": "float64",
    "line_price": "float64",
}

MARGINEDGE_CATALOG_VENDORS_SCHEMA = {
    "vendor_id": "int64",
    "central_vendor_id": "int64",
    "vendor_name": "string",
    "vendor_accounts": "json"
}


MARGINEDGE_CATALOG_PURCHAISE_CATEGORIES = {
    "category_id": "int64",
    "category_name": "string",
    "category_type": "string",
    "accounting_code": "string"
}


##___________________________ TOAST ______________________________

TOAST_REFUND_DAILY_SUMMARY = {
    "guid": "string",
    "yyyyMMdd": "date",
    "refund_amount": "float64",
    "tip_refund_amount": "float64"
}


TOAST_LABOR_TIME_ENTRIES = {
    "time_entry_guid": "string",
    "employee_guid": "string", 
    "in_date": "datetime",
    "out_date": "datetime",
    "regular_hours": "float64",
    "overtime_hours": "float64",
    "total_hours": "float64",
    "hourly_wage": "float64",
    "regular_pay": "float64",
    "overtime_pay": "float64",
    "total_pay": "float64",
    "deleted": "bool",
    "yyyyMMdd": "date",
    "title": "string"
}


TOAST_ITEM_SALES = {
    "check_guid": "string",
    "selection_guid": "string", 
    "item_display_name": "string",
    "item_guid": "string",
    "sales_category_guid": "string",
    "item_voided": "bool",
    "quantity": "float64",
    "price": "float64",
    "pre_discount_price": "float64",
    "unit_price": "float64",
    "total_discount": "float64",
    "unit_discount": "float64",
}


TOAST_ORDER_CHECKS = {
    "order_guid": "string",
    "order_voided": "bool",
    "order_deleted": "bool",
    "order_excess_food": "bool",
    "number_of_guests": "int64",
    "check_guid": "string",
    "check_voided": "bool",
    "check_deleted": "bool",
    "check_net_amount": "float64",
    "yyyyMMdd": "date",
    "hour": "int64",
    "paid_hour": "int64",
    "sitting_duration_secs": "int64",
    "dining_option_guid": "string",
    "revenue_center_guid": "string",
    "table_guid": "string",
}

TOAST_CATALOG_TABLES = {
    "table_guid": "string",
    "table_number": "string",
}


TOAST_CATALOG_DINING_OPTIONS = {
    "dining_option_guid": "string",
    "dining_option": "string",
}


TOAST_CATALOG_MENU_ITEMS = {
    "item_guid": "string",
    "item": "string",
}


TOAST_CATALOG_REVENUE_CENTERS = {
    "revenue_center_guid": "string",
    "revenue_center": "string",
}


TOAST_CATALOG_SALES_CATEGORIES = {
    "sales_category_guid": "string",
    "category": "string",
}

## __________________ Open Meteo ____________________________

WEATHER_DAILY_SUMMARY = {
    "yyyymmdd": "date",
    "temperature_2m_max": "float64",
    "temperature_2m_min": "float64",
    "temperature_2m_mean": "float64",
    "apparent_temperature_max": "float64",
    "apparent_temperature_min": "float64",
    "precipitation_sum": "float64",
    "rain_sum": "float64",
    "precipitation_hours": "float64",
    "snowfall_sum": "float64",
    "windspeed_10m_max": "float64",
    "windgusts_10m_max": "float64",
    "relative_humidity_2m_mean": "int64",
    "cloudcover_mean": "int64",
    "shortwave_radiation_sum": "float64",
}
