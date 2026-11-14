"""Step 7 prep: export every table in OLIST.ANALYSIS to CSV for Tableau Public.

Small marts -> dashboard_data/<table>.csv (committed).
Order-level marts (10-20 MB each) -> dashboard_data/local/<table>.csv (git-ignored).
Summary tables for the dashboard come from scripts/05_export_summaries.py.

Run from the repo root:  conda run -n olist python scripts/04_export_marts.py
"""
from pathlib import Path

import snowflake.connector

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "dashboard_data"
LOCAL = OUT / "local"
ORDER_LEVEL = {"MART_DELIVERY_ORDERS", "MART_REVIEW_IMPACT", "MART_PAYMENT_RECONCILIATION"}


def main():
    LOCAL.mkdir(parents=True, exist_ok=True)
    conn = snowflake.connector.connect(connection_name="olist")
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE OLIST_WH")
    tables = [r[0] for r in cur.execute(
        "SELECT table_name FROM OLIST.INFORMATION_SCHEMA.TABLES "
        "WHERE table_schema = 'ANALYSIS' AND table_type = 'BASE TABLE' ORDER BY 1").fetchall()]

    print(f"{'file':<40}{'rows':>10}{'snowflake':>11}{'size MB':>10}")
    for t in tables:
        cur.execute(f"SELECT * FROM OLIST.ANALYSIS.{t}")
        df = cur.fetch_pandas_all()
        df.columns = df.columns.str.lower()
        sf_rows = cur.execute(f"SELECT COUNT(*) FROM OLIST.ANALYSIS.{t}").fetchone()[0]
        path = (LOCAL if t in ORDER_LEVEL else OUT) / f"{t.lower()}.csv"
        df.to_csv(path, index=False)
        assert len(df) == sf_rows, (t, len(df), sf_rows)
        print(f"{str(path.relative_to(OUT)):<40}{len(df):>10,}{sf_rows:>11,}{path.stat().st_size / 1e6:>10.2f}")

    try:
        cur.execute("ALTER WAREHOUSE OLIST_WH SUSPEND")
    except snowflake.connector.errors.ProgrammingError:
        pass
    conn.close()


if __name__ == "__main__":
    main()
