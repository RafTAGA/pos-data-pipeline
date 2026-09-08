"""
modules/db_neon.py

Loads processed DataFrames into their matching pre-existing Neon tables.

replace_table(): for CATALOG tables (full-snapshot re-pull every run). 
                TRUNCATE + INSERT in one transaction so a failed load can't leave the table half-empty, and so the table's existing schema/constraints are preserved (unlike to_sql(if_exists='replace'), which drops/recreates).

upsert_table(): for FACT tables (orders, labor, sales).
"""

import ast
import json
import os 
import pandas as pd   
from sqlalchemy import create_engine, text  # type: ignore


def _fix_json_columns(df: pd.DataFrame, json_columns: list[str]) -> pd.DataFrame:
    """
    Converts columns holding Python-repr strings (single-quoted, e.g.
    "[{'vendorAccountNumber': 'X'}]") into valid JSON strings (double-quoted),
    so they can be inserted into a jsonb column. Postgres's jsonb type
    requires valid JSON and will reject Python's str() repr as-is.
    """
    df = df.copy()
    for col in json_columns:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: json.dumps(ast.literal_eval(v)) if isinstance(v, str) else json.dumps(v)
            )
    return df


def _require_environment(var_name: str) -> str:
    """
    Reads a NEON required environment variable, exits with code 1 if missing.
    Args:
        var_name: string of the vairable to extract.
   
    Returns:
        value: str of the extracted variable.
    """
    value = os.environ.get(var_name)
    if not value:
        print(f"ERROR: required environment variable {var_name} is not set.")
        exit(1)
    return value


def get_neon_engine():
    """
    Builds a SQLAlchemy engine from the Neon connection string in GitHub Secrets (NEON_CONNECTION_STRING). 
    Uses _require_environment  from the connection string Neon secret
    Args:
        None
    
    Returns: 
        None
    """
    connection_string = _require_environment("NEON_CONNECTION_STRING")
    return create_engine(connection_string)


def enforce_schema(df: pd.DataFrame, schema: dict[str, str]) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    schema = {key.lower(): value for key, value in schema.items()}

    missing = [c for c in schema if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing expected columns: {missing}")

    df = df[list(schema.keys())].copy()  # drops year/year_month/year_week automatically

    for col, dtype in schema.items():
        if dtype == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif dtype == "datetime":
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif dtype == "int64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif dtype == "float64":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif dtype == "bool":
            df[col] = df[col].astype("boolean")
        elif dtype == "string":
            df[col] = df[col].astype("string")
        elif dtype == "json":
            df[col] = df[col].apply(
                lambda v: json.dumps(ast.literal_eval(v)) if isinstance(v, str) else json.dumps(v)
            )

    return df


def get_last_extracted_date(engine, table_name: str, date_column: str = "yyyymmdd"):
    """
    Returns the most recent date already loaded into table_name (None if the
    table is empty). Lets scheduled extraction runs resume from the day after
    whatever was last successfully written to Neon, instead of a fixed date
    range that never advances.
    Args:
      engine: SQLAlchemy engine connected to Neon
      table_name: table to check (must already exist)
      date_column: the table's date column, "yyyymmdd" for every table in this project

    Returns:
      date of the most recent row, or None if the table has no rows yet.
    """
    with engine.connect() as conn:
        return conn.execute(text(f'SELECT MAX("{date_column}") FROM "{table_name}"')).scalar()


def replace_table(engine, table_name: str, table_df:pd.DataFrame) -> int:
    """
    Fully supersedes a Neon table's contents with df, via TRUNCATE + INSERT inside a single transaction. 
    For small catalog/dimension tables that are re-extracted as a complete snapshot every run.
    Args:
      engine: SQLAlchemy engine connected to Neon, output of get_neon_engine()
      table_name: exact Neon table name (must already exist)
      table_df: DataFrame with columns matching the table's schema

    Returns:
      Number of rows written. Returns 0 and skips the write if table_df is empty,
      to avoid wiping a table with an empty/failed upstream extraction.
    """
    if table_df.empty:
        print(f"[{table_name}] WARNING: incoming DataFrame is empty — skipping to avoid wiping the table.")
        return 0

    df = table_df.rename(columns=str.lower)  # match Postgres's lowercased column names
    if table_name == "catalog_vendors":
        df = _fix_json_columns(df, ["vendor_accounts"])

    with engine.begin() as conn:
        conn.execute(text(f'TRUNCATE TABLE "{table_name}"'))
        df.to_sql(name=table_name, con=conn, if_exists="append", index=False)

    print(f"[{table_name}] Replaced: {len(df)} rows written.")
    return len(df)


def replace_catalog_tables(engine, table_to_df: dict[str, pd.DataFrame]) -> dict:
    """
    Runs replace_table() for each entry in table_to_df, continuing past individual failures so one bad catalog doesn't block the others.
    Args:
      engine: SQLAlchemy engine connected to Neon
      table_to_df: dict of {neon_table_name: DataFrame} to fully replace

    Returns:
      dict of {table_name: rows_written or "FAILED: <e>"}
    """
    results = {}
    for table_name, df in table_to_df.items():
        try:
            results[table_name] = replace_table(engine=engine, 
                                                table_name=table_name, 
                                                table_df=df)
        except Exception as e:
            print(f"[{table_name}] FAILED: {e}")
            results[table_name] = f"FAILED: {e}"
    
    return results


def upsert_table(engine, table_name:str, df:pd.DataFrame, key_columns:list[str]):
    """
    Inserts new rows and updates existing ones (matched on key_columns) into a fact table, 
    without touching rows already in the table that aren't part of this batch. 
    Requires an unique identifier already existing on key_columns in the
    target table.
    ON CONFLICT needs Postgres to know which columns define "this row already exists."

    Args:
      engine: SQLAlchemy engine connected to Neon
      table_name: target Neon table name (must already exist, with a unique constraint on key_columns)
      df: DataFrame of rows to upsert.
      key_columns: list of column names forming the natural key (e.g.["order_guid"] or ["time_entry_guid"])

    Returns:
      Number of rows upserted. Returns 0 and skips if df is empty.
    """

    if df.empty: 
        print(f"[{table_name}] WARNING: incoming DataFrame is empty — skipping upsert.")
        return 0

    staging_table = f"_staging_{table_name}"
    update_columns = [col for col in df.columns if col not in key_columns]
    conflict_cols = ", ".join(key_columns)
    update_clause = ", ".join(f'"{up_col}" = EXCLUDED."{up_col}"' for up_col in update_columns)

    with engine.begin() as conn:
        df.to_sql(staging_table, con=conn, if_exists="replace", index=False)

        conn.execute(text(
                            f'''
                              INSERT INTO "{table_name}" ({", ".join(f'"{col}"' for col in df.columns)})
                              SELECT {", ".join(f'"{col}"' for col in df.columns)} FROM "{staging_table}"
                              ON CONFLICT ({conflict_cols})
                              DO UPDATE SET {update_clause}
                           '''
                        ))

        conn.execute(text(f'DROP TABLE "{staging_table}"'))

    print(f"[{table_name}] Upserted: {len(df)} rows.")
    return len(df)