"""Step 1: load the 9 Olist CSVs from data/raw/ into Snowflake OLIST.RAW.

Auth: key-pair via the [olist] connection in ~/.snowflake/connections.toml
(private key at ~/.snowflake/rsa_key.p8 -- never in this repo).

Run from the repo root:  conda run -n olist python scripts/00_load_raw.py
"""
import csv
import sys
from pathlib import Path

import snowflake.connector

REPO = Path(__file__).resolve().parent.parent
RAW_DIR = REPO / "data" / "raw"

# Column names kept exactly as in the source files (renaming happens in dbt staging).
# Zip prefixes are VARCHAR because they carry leading zeros.
TABLES = {
    "CUSTOMERS": ("olist_customers_dataset.csv", """
        customer_id VARCHAR(32), customer_unique_id VARCHAR(32),
        customer_zip_code_prefix VARCHAR(5), customer_city VARCHAR, customer_state VARCHAR(2)"""),
    "GEOLOCATION": ("olist_geolocation_dataset.csv", """
        geolocation_zip_code_prefix VARCHAR(5), geolocation_lat FLOAT, geolocation_lng FLOAT,
        geolocation_city VARCHAR, geolocation_state VARCHAR(2)"""),
    "ORDER_ITEMS": ("olist_order_items_dataset.csv", """
        order_id VARCHAR(32), order_item_id INTEGER, product_id VARCHAR(32), seller_id VARCHAR(32),
        shipping_limit_date TIMESTAMP_NTZ, price NUMBER(10,2), freight_value NUMBER(10,2)"""),
    "ORDER_PAYMENTS": ("olist_order_payments_dataset.csv", """
        order_id VARCHAR(32), payment_sequential INTEGER, payment_type VARCHAR,
        payment_installments INTEGER, payment_value NUMBER(10,2)"""),
    "ORDER_REVIEWS": ("olist_order_reviews_dataset.csv", """
        review_id VARCHAR(32), order_id VARCHAR(32), review_score INTEGER,
        review_comment_title VARCHAR, review_comment_message VARCHAR,
        review_creation_date TIMESTAMP_NTZ, review_answer_timestamp TIMESTAMP_NTZ"""),
    "ORDERS": ("olist_orders_dataset.csv", """
        order_id VARCHAR(32), customer_id VARCHAR(32), order_status VARCHAR,
        order_purchase_timestamp TIMESTAMP_NTZ, order_approved_at TIMESTAMP_NTZ,
        order_delivered_carrier_date TIMESTAMP_NTZ, order_delivered_customer_date TIMESTAMP_NTZ,
        order_estimated_delivery_date TIMESTAMP_NTZ"""),
    "PRODUCTS": ("olist_products_dataset.csv", """
        product_id VARCHAR(32), product_category_name VARCHAR,
        product_name_lenght INTEGER, product_description_lenght INTEGER, product_photos_qty INTEGER,
        product_weight_g INTEGER, product_length_cm INTEGER, product_height_cm INTEGER,
        product_width_cm INTEGER"""),
    "SELLERS": ("olist_sellers_dataset.csv", """
        seller_id VARCHAR(32), seller_zip_code_prefix VARCHAR(5), seller_city VARCHAR,
        seller_state VARCHAR(2)"""),
    "PRODUCT_CATEGORY_NAME_TRANSLATION": ("product_category_name_translation.csv", """
        product_category_name VARCHAR, product_category_name_english VARCHAR"""),
}

SETUP_SQL = [
    "CREATE WAREHOUSE IF NOT EXISTS OLIST_WH WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 "
    "AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE",
    "ALTER WAREHOUSE OLIST_WH SET WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60",
    "USE WAREHOUSE OLIST_WH",
    "CREATE DATABASE IF NOT EXISTS OLIST",
    "CREATE SCHEMA IF NOT EXISTS OLIST.RAW",
    "USE SCHEMA OLIST.RAW",
    # Quoted fields may contain commas/newlines (review comments); empty fields -> NULL.
    """CREATE OR REPLACE FILE FORMAT OLIST_CSV TYPE = CSV SKIP_HEADER = 1
       FIELD_OPTIONALLY_ENCLOSED_BY = '"' EMPTY_FIELD_AS_NULL = TRUE
       SKIP_BYTE_ORDER_MARK = TRUE ENCODING = 'UTF8'""",
]


def csv_row_count(path: Path) -> int:
    """Count data records with a real CSV parser (handles quoted newlines)."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # minus header


def main() -> int:
    conn = snowflake.connector.connect(connection_name="olist")
    cur = conn.cursor()
    try:
        for sql in SETUP_SQL:
            cur.execute(sql)

        results = []
        for table, (filename, columns) in TABLES.items():
            path = RAW_DIR / filename
            cur.execute(f"CREATE OR REPLACE TABLE {table} ({columns})")
            cur.execute(f"PUT 'file://{path}' @%{table} AUTO_COMPRESS = TRUE OVERWRITE = TRUE")
            cur.execute(
                f"COPY INTO {table} FROM @%{table} FILE_FORMAT = (FORMAT_NAME = OLIST_CSV) "
                "ON_ERROR = ABORT_STATEMENT PURGE = TRUE"
            )
            sf_rows = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            csv_rows = csv_row_count(path)
            results.append((table, csv_rows, sf_rows))
            print(f"loaded {table}", flush=True)

        print(f"\n{'table':<36}{'csv_rows':>10}{'snowflake_rows':>16}  match")
        all_match = True
        for table, csv_rows, sf_rows in results:
            ok = csv_rows == sf_rows
            all_match &= ok
            print(f"{table:<36}{csv_rows:>10}{sf_rows:>16}  {'OK' if ok else 'MISMATCH'}")

        try:
            cur.execute("ALTER WAREHOUSE OLIST_WH SUSPEND")  # stop credits now
        except snowflake.connector.errors.ProgrammingError:
            pass  # already suspended
        return 0 if all_match else 1
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
