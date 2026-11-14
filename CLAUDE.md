# Olist Marketplace Operations Analytics

## Project goal
End-to-end analysis of ~100K real orders from Olist, a Brazilian e-commerce marketplace
(Kaggle: "Brazilian E-Commerce Public Dataset by Olist"). Raw data is loaded into
**Snowflake**, modeled into a star schema with **dbt**, analyzed in **Python**, and presented
in a **Tableau Public** dashboard. Everything lives in this public GitHub repo.

## Business questions
1. **Delivery operations:** How often do orders arrive later than promised, and what drives it
   (seller, region, shipping lane, distance)?
2. **Customer impact:** Do late deliveries lower review scores and repeat purchases?
3. **Retention:** How many customers come back, and how does that differ by first-order experience?
4. **Finance reconciliation:** Do payments tie out to item prices plus freight? Where don't they, and why?
5. **Cost to serve:** What share of order value goes to freight, by region and category?

## Setup
- macOS, Anaconda
- Conda env: `olist` (Python 3.11) — activate with `conda activate olist`
- Packages: pandas, pyarrow, jupyter, matplotlib, scipy, statsmodels, dbt-snowflake (dbt Core 1.x),
  snowflake-connector-python (with pandas support)
- Raw data: the 9 Olist CSVs live in `data/raw/` (git-ignored, never committed)
- `olist_project_guide.md` is a local build guide (git-ignored)

## Snowflake (settings only — no secrets)
- **Trial ends around Dec 14, 2026.** Finish Steps 1–5 (and export marts) before then.
- Account identifier: `SCKLCWV-CS18531` (locator `QT02634`, region AWS_US_EAST_2)
- User: `DAVEDEV1120`, role: `SYSADMIN`
- Auth: key-pair (`SNOWFLAKE_JWT`). Private key `~/.snowflake/rsa_key.p8` (outside repo, chmod 600);
  public key registered via `ALTER USER ... SET RSA_PUBLIC_KEY` in Snowsight.
- Connection config: `[olist]` in `~/.snowflake/connections.toml` — Python uses
  `snowflake.connector.connect(connection_name="olist")`.
- Warehouse `OLIST_WH` (XSMALL, AUTO_SUSPEND = 60, AUTO_RESUME = TRUE)
- Database `OLIST`, schema `RAW` — 9 tables loaded by `scripts/00_load_raw.py`
  (original column names, typed; zip prefixes VARCHAR to keep leading zeros)

### Raw load row counts (CSV = Snowflake, verified 2026-11-14)
| Table | Rows |
|---|---:|
| CUSTOMERS | 99,441 |
| GEOLOCATION | 1,000,163 |
| ORDER_ITEMS | 112,650 |
| ORDER_PAYMENTS | 103,886 |
| ORDER_REVIEWS | 99,224 |
| ORDERS | 99,441 |
| PRODUCTS | 32,951 |
| SELLERS | 3,095 |
| PRODUCT_CATEGORY_NAME_TRANSLATION | 71 |

## Raw data-quality findings (Step 2, from `docs/raw_profile.md`)
- `customer_id` is one-per-order (99,441 ids, each with exactly 1 order); the person is
  `customer_unique_id` (96,096 distinct; 2,997 of them have 2+ customer_ids, max 17).
- Order status: 96,478 delivered; 2,963 in other statuses (shipped 1,107, canceled 625,
  unavailable 609, invoiced 314, processing 301, created 5, approved 2).
- Delivery timestamps: 2,965 orders lack `order_delivered_customer_date`; 8 of them are
  status `delivered`. 6 non-delivered orders do have a delivery date. 166 orders show carrier
  pickup before purchase; 23 show customer delivery before carrier pickup.
- Reviews: `review_id` is NOT unique — 789 review_ids appear on multiple orders (1,603 rows).
  (`review_id`, `order_id`) is unique. 547 orders have 2–3 reviews; 768 orders have none.
- Geolocation: 1,000,163 rows over 19,015 zip prefixes (median 29 rows per zip, max 1,146);
  261,831 exact duplicate rows; 8 zips span >1 state; 42 rows outside Brazil's bounding box.
  Missing from geolocation: 157 customer zip prefixes (278 customers), 7 seller zips (7 sellers).
- Thin months (<10% of median 4,285): 2016-09 (4), 2016-10 (324), 2016-11 (0), 2016-12 (1),
  2018-09 (16), 2018-10 (4). Analysis window to be decided before Step 5.
- Payments vs items + freight per order: 98,362 match (|diff| ≤ 0.01); 264 pay more; 39 pay
  less; 775 orders have payments but no items; 1 order has items but no payments.
- Products: 610 have no category (and no name/description/photo fields); 2 categories
  (13 products) are missing from the English translation table.

## Analysis definitions
Committed before any modeling (Step 3). Change only with a new, explained commit.

- **Analysis window:** orders purchased 2017-01-01 to 2018-08-31. Excludes the thin months
  2016-09 to 2016-12 and 2018-09 to 2018-10. Jan 2017 is kept despite being small (800 orders).
- **Customer:** `customer_unique_id`, never `customer_id`.
- **Delivered order (`is_delivered_with_date`):** `order_status = 'delivered'` and
  `order_delivered_customer_date` is not null.
- **Impossible timestamps (`has_impossible_timestamps`):** any of approved before purchase,
  carrier pickup before purchase, customer delivery before carrier pickup, customer delivery
  before purchase. These orders are excluded from delivery metrics only, and the count excluded
  is reported.
- **Delivery metrics use:** delivered orders in the window without impossible timestamps.
- **Late:** delivered on a later date than `order_estimated_delivery_date`, comparing dates not
  timestamps, since the estimate is always midnight.
- **Days late:** days from estimated delivery date to actual delivery date; negative means early.
- **Review for an order (`is_latest_review_for_order`):** the review with the latest
  `review_answer_timestamp`, ties broken by `review_creation_date` then `review_id`. Orders with
  no review are excluded from review analysis only.
- **First order:** a customer's earliest order by purchase time.
- **Repeat purchase (`repeat_within_180d`):** a qualifying order (not canceled or unavailable)
  placed after the customer's first order and within 180 days of it (purchase date ≤ first
  purchase date + 180 days).
- **Review-impact comparisons (`has_full_followup`):** only first orders purchased 2017-01-01 to
  2018-02-28, so every customer has a full 180-day follow-up inside the analysis window.
  *(Changed 2026-11-14, before any analysis: replaces "any later order in the window", which
  gave later first orders less time to repeat.)*
- **Cohort retention:** cohort is the month of first purchase. A customer is retained in month N
  if they place a qualifying order N months later, N = 1 to 6. Only cohorts with a full 6 months
  of follow-up are reported: first purchase Jan 2017 to Feb 2018.
- **Payment match:** absolute difference between payment total and item price plus freight is
  0.01 BRL or less.
- **Freight share:** freight total / (item total + freight total).
- **Geolocation point:** median lat/long per zip prefix, after dropping points outside Brazil
  (lat -34 to 5.5, lng -74 to -34).

## dbt
- Project: `olist_dbt/` (dbt Core 1.12, dbt-snowflake). Profile `olist_dbt` in `~/.dbt/profiles.yml`
  (key-pair, not in repo). Run dbt commands from inside `olist_dbt/`.
- Schemas: custom schema names used as-is (`macros/generate_schema_name.sql`) → `OLIST.STAGING`,
  later `OLIST.CORE`, `OLIST.ANALYSIS`.
- Analysis window lives in `dbt_project.yml` vars `analysis_start_date` / `analysis_end_date`.

### Staging counts (Step 3, `docs/staging_counts.md`)
- All 9 staging models match raw row counts (stg_geolocation = 19,015 = distinct zip prefixes).
- Orders in analysis window: 99,092. Delivered with date: 96,470. Impossible timestamps: 189.
- Delivery-metric base: 96,203 in window and delivered with date; 184 of those excluded for
  impossible timestamps → 96,019.
- One latest review per reviewed order: 98,673.
- Geolocation: 42 points outside Brazil dropped; 5 zips have no valid point (null coordinates).
- Products: 610 without category; 13 with an untranslated category (English name falls back to Portuguese).

### Core star schema (Step 4, `docs/core_counts.md`)
- `OLIST.CORE` tables and grain: dim_customers (customer_unique_id, 96,096), dim_sellers
  (seller_id, 3,095), dim_products (product_id, 32,951), dim_date (day 2016-01-01..2020-12-31,
  1,827), fct_orders (order_id, 99,441), fct_order_items (order_id + order_item_id, 112,650).
- fct_orders aggregates items/payments/reviews to order level before joining; totals equal
  staging exactly (no fan-out). days_late / is_late are null unless is_delivered_with_date.
- dbt build: 40 pass, 1 warn. Warn = `assert_every_order_has_item` → 775 orders without items
  (unavailable 603, canceled 164, created 5, invoiced 2, shipped 1; all have payments).

### Analysis marts (Step 5, `OLIST.ANALYSIS`) — row counts only, no metrics reported yet
| Mart | Grain | Rows |
|---|---|---:|
| mart_delivery_orders | order in delivery base | 96,019 |
| mart_delivery_performance | (dimension, group): customer_state 27, seller_state 22, lane 410, purchase_month 20 | 479 |
| mart_review_impact | customer's first order (customer_unique_id) | 96,096 |
| mart_cohort_retention | (cohort_month Jan 2017–Feb 2018, month_number 1–6) | 84 |
| mart_payment_reconciliation | order (all orders) | 99,441 |
| mart_cost_to_serve | (dimension, group): customer_state 27, product_category 74 | 101 |

Design choices made in Step 5 (not in the definitions above):
- **Primary seller:** for lane / seller_state / distance, an order uses the seller with the largest
  price + freight in the order (ties → lowest order_item_id); `is_multi_seller` flags the 1,249
  base orders with >1 seller (499 with sellers in >1 state).
- **Distance:** Snowflake `HAVERSINE()` (km) between seller and customer zip median points; null
  if either point is missing.
- **Cohort size:** all customers whose first purchase falls in the month, any status.
- **Cost-to-serve base:** in-window orders with items, not canceled/unavailable. Category is
  item-level; untranslated categories use the Portuguese name; no category → `unknown`.
- **Reconciliation categories** (first match wins): no_items_no_payments → payment_without_items
  → items_without_payment → matches (|diff| ≤ 0.01) → installment_interest (pays more + credit
  card with >1 installment) → voucher_overpayment (pays more + voucher, no installments) →
  unexplained (all underpayments and other overpayments). 5–6 are consistent-with, not proven.
- dbt build: 64 pass, 1 warn (the known 775 orders without items).

## Rules
- **Explain each command before running it.**
- **Never commit credentials or raw data.** No passwords, private keys (`*.p8`, `*.pem`), `.env`
  files, or CSVs from `data/raw/`. Snowflake keys live in `~/.snowflake/`, dbt profiles in `~/.dbt/`.
- **Commit after each step.**
- **Never report findings that weren't computed.** Every number must come from code that was
  actually run against the data.

## Progress
- [x] Step 0 — repo, conda env, .gitignore, raw CSVs in `data/raw/`
- [x] Step 1 — Snowflake key-pair auth, OLIST_WH / OLIST.RAW, 9 tables loaded, row counts verified
- [x] Step 2 — raw profile (`scripts/01_profile_raw.py` → `docs/raw_profile.md`)
- [x] Step 3 — dbt staging (9 models in `OLIST.STAGING`, counts in `docs/staging_counts.md`)
- [x] Step 4 — star schema in `OLIST.CORE` + dbt tests (40 pass, 1 expected warn)
- [x] Step 5 — analysis marts in `OLIST.ANALYSIS` + tests (64 pass, 1 expected warn)
