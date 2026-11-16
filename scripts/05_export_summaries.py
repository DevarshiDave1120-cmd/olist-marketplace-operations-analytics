"""Step 7 prep: small summary tables for Tableau Public, written to dashboard_data/summary_*.csv.

Recomputes each number from OLIST.ANALYSIS (same logic as notebooks/olist_analysis.ipynb), then
checks every value against the numbers recorded in the project notes (Step 6 results), rounded to the
precision recorded there. Exits non-zero on any mismatch.

Run from the repo root:  conda run -n olist python scripts/05_export_summaries.py
"""
import sys
from pathlib import Path

import pandas as pd
import snowflake.connector

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "dashboard_data"
BAND_LABELS = ["0–100", "100–250", "250–500", "500–1,000", "1,000–2,000", "2,000+"]

conn = snowflake.connector.connect(connection_name="olist")
cur = conn.cursor()
cur.execute("USE WAREHOUSE OLIST_WH")
cur.execute("USE DATABASE OLIST")


def q(sql):
    cur.execute(sql)
    df = cur.fetch_pandas_all()
    df.columns = df.columns.str.lower()
    return df


def one(sql):
    return cur.execute(sql).fetchone()[0]


# --- 1. KPIs -----------------------------------------------------------------------------------
d = q("""SELECT COUNT(*) AS n, COUNT_IF(is_late) AS late, MEDIAN(days_late) AS med_days_late
         FROM ANALYSIS.MART_DELIVERY_ORDERS""").iloc[0]
rv = q("""SELECT is_late,
                 COUNT_IF(has_review)                          AS reviews,
                 AVG(IFF(has_review, review_score, NULL))      AS avg_score,
                 COUNT_IF(has_review AND review_score <= 2)    AS low_star,
                 COUNT(*)                                      AS customers,
                 COUNT_IF(repeat_within_180d)                  AS repeaters
          FROM ANALYSIS.MART_REVIEW_IMPACT
          WHERE has_full_followup AND is_in_delivery_base
          GROUP BY is_late""").set_index("is_late")
ret = q("""SELECT month_number, AVG(retention_rate) AS mean_of_cohorts,
                  SUM(retained_customers) / SUM(cohort_size) AS pooled
           FROM ANALYSIS.MART_COHORT_RETENTION GROUP BY 1""").set_index("month_number")
freight_share = one("""SELECT SUM(freight_total) / (SUM(item_total) + SUM(freight_total))
                       FROM ANALYSIS.MART_COST_TO_SERVE WHERE dimension = 'customer_state'""")
match_rate = one("""SELECT COUNT_IF(reason_category = 'matches') / COUNT(*)
                    FROM ANALYSIS.MART_PAYMENT_RECONCILIATION""")

L, O = rv.loc[True], rv.loc[False]
kpis = pd.DataFrame([
    ("delivery_base_orders", int(d.n), "orders", "delivered, in window, no impossible timestamps"),
    ("late_rate", d.late / d.n, "share", "delivery base"),
    ("median_days_early", -float(d.med_days_late), "days", "delivery base; median of estimate minus delivered date"),
    ("avg_review_late", float(L.avg_score), "score 1-5", "first orders, full follow-up, reviewed"),
    ("avg_review_on_time", float(O.avg_score), "score 1-5", "first orders, full follow-up, reviewed"),
    ("low_star_share_late", L.low_star / L.reviews, "share", "share of 1-2 star reviews"),
    ("low_star_share_on_time", O.low_star / O.reviews, "share", "share of 1-2 star reviews"),
    ("repeat_rate_180d_late", L.repeaters / L.customers, "share", "first orders, full follow-up"),
    ("repeat_rate_180d_on_time", O.repeaters / O.customers, "share", "first orders, full follow-up"),
    ("repeat_rate_180d_all", (L.repeaters + O.repeaters) / (L.customers + O.customers), "share",
     "first orders, full follow-up, in delivery base"),
    ("retention_month_1_mean", float(ret.loc[1, "mean_of_cohorts"]), "share", "mean of 14 cohort rates"),
    ("retention_month_6_mean", float(ret.loc[6, "mean_of_cohorts"]), "share", "mean of 14 cohort rates"),
    ("retention_month_1_pooled", float(ret.loc[1, "pooled"]), "share", "all cohort customers pooled"),
    ("retention_month_6_pooled", float(ret.loc[6, "pooled"]), "share", "all cohort customers pooled"),
    ("freight_share", float(freight_share), "share", "freight / (items + freight), cost-to-serve base"),
    ("reconciliation_match_rate", float(match_rate), "share", "orders with |payment - (items + freight)| <= 0.01"),
], columns=["metric", "value", "unit", "definition"])

# --- 2. Distance bins --------------------------------------------------------------------------
bins = q("""
    WITH o AS (
        SELECT CASE WHEN distance_km < 100  THEN 1 WHEN distance_km < 250  THEN 2
                    WHEN distance_km < 500  THEN 3 WHEN distance_km < 1000 THEN 4
                    WHEN distance_km < 2000 THEN 5 ELSE 6 END AS band_order,
               is_late, days_late,
               DATEDIFF(day, purchase_date, estimated_delivery_date) AS promised_days,
               DATEDIFF(day, purchase_date, delivered_date)          AS actual_days
        FROM ANALYSIS.MART_DELIVERY_ORDERS
        WHERE distance_km IS NOT NULL)
    SELECT band_order, COUNT(*) AS orders, COUNT_IF(is_late) / COUNT(*) AS late_rate,
           MEDIAN(promised_days) AS median_promised_days, MEDIAN(actual_days) AS median_actual_days,
           -MEDIAN(days_late) AS median_buffer_days,
           PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY actual_days) AS p90_actual_days
    FROM o GROUP BY 1 ORDER BY 1""")
bins.insert(1, "distance_band_km", [BAND_LABELS[i - 1] for i in bins.band_order])

# --- 3. Review timing (answered before vs on/after delivery) ------------------------------------
timing = q("""
    SELECT IFF(r.is_late, 'late', 'on-time') AS delivery_group,
           IFF(s.review_answered_at < o.delivered_at, 'answered before delivery',
               'answered on/after delivery') AS review_timing,
           COUNT(*) AS reviews, AVG(r.review_score) AS mean_score,
           COUNT_IF(r.review_score <= 2) / COUNT(*) AS low_star_share
    FROM ANALYSIS.MART_REVIEW_IMPACT r
    JOIN CORE.FCT_ORDERS o            ON o.order_id = r.first_order_id
    JOIN STAGING.STG_ORDER_REVIEWS s  ON s.review_id = o.review_id AND s.order_id = o.order_id
    WHERE r.has_full_followup AND r.is_in_delivery_base AND r.has_review
    GROUP BY 1, 2 ORDER BY 1, 2""")

# --- 4. Reconciliation --------------------------------------------------------------------------
ORDER = ["matches", "installment_interest", "voucher_overpayment", "unexplained",
         "payment_without_items", "items_without_payment", "no_items_no_payments"]
recon = q("""
    SELECT reason_category, COUNT(*) AS orders,
           COALESCE(SUM(payment_total), 0)      AS payment_value_brl,
           COALESCE(SUM(items_plus_freight), 0) AS items_plus_freight_brl,
           COALESCE(SUM(difference), 0)         AS net_difference_brl
    FROM ANALYSIS.MART_PAYMENT_RECONCILIATION GROUP BY 1""").set_index("reason_category")
recon = recon.reindex(ORDER).fillna(0)
recon["orders"] = recon.orders.astype(int)
recon["share_of_orders"] = recon.orders / recon.orders.sum()
recon["share_of_payment_value"] = recon.payment_value_brl / recon.payment_value_brl.sum()
# True = reason is an explanation consistent with the payment data, not a proven cause.
recon["is_inferred_explanation"] = recon.index.isin(["installment_interest", "voucher_overpayment"])
recon = recon.reset_index()

# --- 5. Lanes (>= 100 orders) -------------------------------------------------------------------
lanes = q("""
    SELECT group_value AS lane, order_count AS orders, late_count AS late_orders,
           late_rate, late_count / (SELECT COUNT_IF(is_late) FROM ANALYSIS.MART_DELIVERY_ORDERS)
               AS share_of_all_late
    FROM ANALYSIS.MART_DELIVERY_PERFORMANCE
    WHERE dimension = 'lane' AND order_count >= 100
    ORDER BY late_orders DESC, lane""")

try:
    cur.execute("ALTER WAREHOUSE OLIST_WH SUSPEND")
except snowflake.connector.errors.ProgrammingError:
    pass
conn.close()

# --- Write ---------------------------------------------------------------------------------------
files = {"summary_kpis.csv": kpis, "summary_distance_bins.csv": bins,
         "summary_review_timing.csv": timing, "summary_reconciliation.csv": recon,
         "summary_lanes.csv": lanes}
for name, df in files.items():
    for c in df.columns:
        if df[c].dtype == object:  # Snowflake NUMBER arrives as Decimal objects
            try:
                df[c] = pd.to_numeric(df[c])
            except (ValueError, TypeError):
                pass  # genuine text column
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].round(6)
    df.to_csv(OUT / name, index=False)

# --- Check against recorded results -------------------------------------------------------------
# Values transcribed from the recorded Step 6a/6b/6c results; pct = compare value*100.
fails, checks = [], 0


def check(label, actual, expected, decimals=0, pct=False):
    global checks
    checks += 1
    a = float(actual) * (100 if pct else 1)
    if round(a, decimals) != round(expected, decimals):
        fails.append(f"{label}: file {a:.{decimals + 2}f} vs recorded {expected}")


k = kpis.set_index("metric").value
check("delivery base", k.delivery_base_orders, 96019)
check("late rate", k.late_rate, 6.80, 2, True)
check("median days early", k.median_days_early, 12)
check("avg review late", k.avg_review_late, 2.18, 2)
check("avg review on-time", k.avg_review_on_time, 4.27, 2)
check("1-2 star late", k.low_star_share_late, 65.39, 2, True)
check("1-2 star on-time", k.low_star_share_on_time, 9.46, 2, True)
check("repeat late", k.repeat_rate_180d_late, 2.67, 2, True)
check("repeat on-time", k.repeat_rate_180d_on_time, 3.20, 2, True)
check("retention m1 mean", k.retention_month_1_mean, 0.48, 2, True)
check("retention m6 mean", k.retention_month_6_mean, 0.26, 2, True)
check("retention m1 pooled", k.retention_month_1_pooled, 0.48, 2, True)
check("retention m6 pooled", k.retention_month_6_pooled, 0.23, 2, True)
check("freight share", k.freight_share, 14.25, 2, True)
check("match rate", k.reconciliation_match_rate, 98.91, 2, True)
check("repeat late (customers)", L.customers, 3664)
check("repeat on-time (customers)", O.customers, 51515)
check("reviews late", L.reviews, 3577)
check("reviews on-time", O.reviews, 51193)

exp_bins = {"orders": [17819, 9386, 27445, 25619, 9686, 5586],
            "late_rate": [4.5, 4.9, 6.6, 7.2, 9.5, 12.1],
            "median_promised_days": [15, 20, 23, 26, 30, 34],
            "median_actual_days": [5, 8, 10, 12, 15, 18],
            "median_buffer_days": [9, 12, 13, 14, 14, 14],
            "p90_actual_days": [12, 16.5, 21, 24, 30, 35]}
for col, vals in exp_bins.items():
    for band, a, e in zip(bins.distance_band_km, bins[col], vals):
        check(f"bins {band} {col}", a, e, 1 if col in ("late_rate", "p90_actual_days") else 0,
              col == "late_rate")

exp_timing = {("late", "answered before delivery"): (2597, 1.62, 82.1),
              ("late", "answered on/after delivery"): (980, 3.65, 21.2),
              ("on-time", "answered before delivery"): (93, 4.06, 11.8),
              ("on-time", "answered on/after delivery"): (51100, 4.27, 9.5)}
t = timing.set_index(["delivery_group", "review_timing"])
for key, (n, m, s) in exp_timing.items():
    check(f"timing {key} reviews", t.loc[key, "reviews"], n)
    check(f"timing {key} mean", t.loc[key, "mean_score"], m, 2)
    check(f"timing {key} 1-2 star", t.loc[key, "low_star_share"], s, 1, True)

exp_recon = {"matches": (98362, 15793088.11, 98.91, 98.65),
             "payment_without_items": (775, 162591.95, 0.78, 1.02),
             "installment_interest": (249, 37129.67, 0.25, 0.23),
             "unexplained": (50, 15813.72, 0.05, 0.10),
             "voucher_overpayment": (4, 248.67, None, None),
             "items_without_payment": (1, 0.0, None, None),
             "no_items_no_payments": (0, 0.0, None, None)}
r = recon.set_index("reason_category")
for cat, (n, v, so, sv) in exp_recon.items():
    check(f"recon {cat} orders", r.loc[cat, "orders"], n)
    check(f"recon {cat} payment value", r.loc[cat, "payment_value_brl"], v, 2)
    if so is not None:
        check(f"recon {cat} share of orders", r.loc[cat, "share_of_orders"], so, 2, True)
        check(f"recon {cat} share of value", r.loc[cat, "share_of_payment_value"], sv, 2, True)
check("recon installment net diff", r.loc["installment_interest", "net_difference_brl"], 3063.69, 2)
check("recon unexplained net diff", r.loc["unexplained", "net_difference_brl"], -196.72, 2)
check("recon items_without_payment items+freight", r.loc["items_without_payment", "items_plus_freight_brl"], 143.46, 2)
check("recon total payments", recon.payment_value_brl.sum(), 16008872.12, 2)

exp_lanes = {  # lane: (orders, late orders, late rate %, share of all late % or None)
    "SP→SP": (30627, 1426, 4.7, 21.8), "SP→RJ": (8124, 1152, 14.2, 17.6),
    "SP→MG": (7407, 393, 5.3, None), "SP→BA": (2302, 297, 12.9, None),
    "SP→RS": (3570, 238, 6.7, None), "SP→SC": (2312, 222, 9.6, None),
    "SP→ES": (1454, 180, 12.4, None), "SP→PR": (3102, 138, 4.4, None),
    "SP→CE": (967, 133, 13.8, None), "PR→RJ": (963, 117, 12.1, None),
    "SP→AL": (255, 61, 23.9, None), "MA→SP": (124, 25, 20.2, None),
    "SP→MA": (486, 93, 19.1, None), "SP→PI": (326, 54, 16.6, None),
    "SP→SE": (206, 34, 16.5, None), "PR→BA": (143, 21, 14.7, None),
    "SP→MS": (475, 59, 12.4, None)}
ln = lanes.set_index("lane")
for lane, (n, lo, lr, sh) in exp_lanes.items():
    check(f"lane {lane} orders", ln.loc[lane, "orders"], n)
    check(f"lane {lane} late orders", ln.loc[lane, "late_orders"], lo)
    check(f"lane {lane} late rate", ln.loc[lane, "late_rate"], lr, 1, True)
    if sh is not None:
        check(f"lane {lane} share of late", ln.loc[lane, "share_of_all_late"], sh, 1, True)
check("lanes with >=100 orders", len(lanes), 70)
check("top-2 lanes share of late", lanes.share_of_all_late.head(2).sum(), 39.5, 1, True)
check("top-10 lanes share of late", lanes.share_of_all_late.head(10).sum(), 65.8, 1, True)

print(f"\n{'file':<32}{'rows':>6}{'size KB':>10}")
for name, df in files.items():
    print(f"{name:<32}{len(df):>6}{(OUT / name).stat().st_size / 1e3:>10.1f}")
check("repeat all", k.repeat_rate_180d_all, 3.16, 2, True)
print(f"checks against recorded results: {checks - len(fails)} of {checks} match")
for f in fails:
    print("  MISMATCH", f)
sys.exit(1 if fails else 0)
