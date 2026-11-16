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
- dbt build (last full run 2026-11-14, `target/run_results.json`): 21 models built; 46 tests, of which
  45 pass and 1 warns (the known 775 orders without items). The 46 tests are 43 generic (17 not_null,
  9 unique, 9 relationships, 5 accepted_values, 3 unique_combination) and 3 singular.
  *(Corrected 2026-11-16: this line said "64 pass, 1 warn", which matched neither the test count nor
  the node count, 66 pass + 1 warn.)*

### Step 6a results — delivery (`notebooks/olist_analysis.ipynb`, computed 2026-11-14)
- Delivery base 96,019 (96,203 delivered in window; 184 excluded for impossible timestamps).
- Late rate 6.80% (6,529 orders; 95% Wilson CI 6.64%–6.96%). Median days late −12 (mean −11.8).
- Rankings use ≥100 orders: 70 of 410 lanes (94.7% of base), 24 of 27 customer states.
- Worst lanes: SP→AL 23.9% (255), MA→SP 20.2% (124), SP→MA 19.1% (486), SP→PI 16.6% (326),
  SP→SE 16.5% (206), PR→BA 14.7% (143), SP→RJ 14.2% (8,124), SP→CE 13.8% (967),
  SP→BA 12.9% (2,302), SP→MS 12.4% (475).
- Worst customer states: AL 21.5% (396), MA 17.6% (710), SE 15.4% (331), PI 14.0% (472), CE 13.8% (1,272).
- Distance (95,541 orders; 478 missing a point): late rate 4.5% (0–100 km) → 12.1% (2,000+ km);
  median days late −9 → −14. Spearman ρ(distance, days late) = −0.18; Pearson r = −0.075;
  point-biserial r(distance, is_late) = 0.076. Chart: `images/6a_distance_vs_lateness.png`.
- Padding test (promised = estimate − purchase date; actual = delivered − purchase date; medians,
  days) by band 0–100 / 100–250 / 250–500 / 500–1,000 / 1,000–2,000 / 2,000+ km:
  promised 15 / 20 / 23 / 26 / 30 / 34; actual 5 / 8 / 10 / 12 / 15 / 18; buffer 9 / 12 / 13 /
  14 / 14 / 14; p90 actual 12 / 16.5 / 21 / 24 / 30 / 35. Chart: `images/6a_promised_vs_actual.png`.
- Lanes (≥100 orders) by late-order count: SP→SP 1,426 (4.7%, 21.8% of all late), SP→RJ 1,152
  (14.2%, 17.6%), SP→MG 393 (5.3%), SP→BA 297 (12.9%), SP→RS 238 (6.7%), SP→SC 222 (9.6%),
  SP→ES 180 (12.4%), SP→PR 138 (4.4%), SP→CE 133 (13.8%), PR→RJ 117 (12.1%). Top 2 = 39.5% of
  late orders; top 10 = 65.8%.

### Step 6b results — review impact (`notebooks/olist_analysis.ipynb`, computed 2026-11-14)
- Population: 96,096 first orders → 57,184 with full follow-up → 55,179 in delivery base
  (3,664 late, 51,515 on-time) → 54,770 with a review (3,577 late, 51,193 on-time).
- Review score (Mann–Whitney U, ordinal): late mean 2.18 vs on-time 4.27; difference −2.09
  (Welch 95% CI −2.14 to −2.04); p < 1e-300; P(late scores higher) = 0.172.
  Score mix late vs on-time: 1★ 56.6% vs 6.6%, 2★ 8.8% vs 2.8%, 3★ 10.2% vs 8.6%,
  4★ 9.1% vs 20.9%, 5★ 15.3% vs 61.0%.
- Share of 1–2 star (two-proportion z): late 65.39% vs on-time 9.46%; difference +55.93 pts
  (Newcombe 95% CI +54.34 to +57.50); p < 1e-300. Within-month CMH OR 17.37 (16.09–18.76), p < 1e-300.
- Repeat within 180 days (two-proportion z): late 2.67% vs on-time 3.20%; difference −0.52 pts
  (95% CI −1.02 to +0.07); p = 0.081 — not significant. Within-month CMH OR 0.84 (0.68–1.03), p = 0.097.
  Overall repeat within 180 days (late + on-time, 55,179 customers): 3.16% (computed in
  `scripts/05_export_summaries.py`).
- Month mix differs: chi-square 1,430.7, dof 13, p = 3.8e-298, Cramér's V = 0.161. Late first
  orders concentrate in 2017-11 (23.9% of late vs 12.0% of on-time; late rate 12.4%) and 2018-02
  (24.3% vs 10.5%; late rate 14.2%). Chart: `images/6b_month_mix.png`.
- Review timing (same 54,770 reviewed first orders). Per the Kaggle data description,
  review_creation_date = survey **sent** date; review_answer_timestamp = customer **answered**.
  - Created (sent) before delivered date: late 76.5% (2,736 of 3,577) vs on-time 0.2% (118 of 51,193).
    Late orders: mean 1.79 before vs 3.45 on/after (diff −1.67, Mann–Whitney p = 5.2e-162);
    1–2 star 77.2% vs 27.1%.
  - Answered before delivered timestamp: late 72.6% (2,597) vs on-time 0.2% (93). Late orders:
    mean 1.62 answered before vs 3.65 on/after (diff −2.03, p = 1.2e-259); 1–2 star 82.1% vs 21.2%.
    On-time: answered before 93 (mean 4.06, 1–2 star 11.8%); answered on/after 51,100 (mean 4.27,
    1–2 star 9.5%).

### Step 6c results (`notebooks/olist_analysis.ipynb`, computed 2026-11-14)
- **Retention** (14 cohorts Jan 2017–Feb 2018, 57,184 customers): month 1–6 retention, mean of
  cohorts 0.48% / 0.35% / 0.25% / 0.31% / 0.23% / 0.26%; pooled 0.48% / 0.36% / 0.26% / 0.29% /
  0.23% / 0.23%. Highest month-1 cohorts: 2017-08 and 2017-10 (0.69%). Chart: `images/6c_cohort_retention.png`.
- **Reconciliation** (99,441 orders; total payments BRL 16,008,872.12):
  matches 98,362 (98.91% of orders; BRL 15,793,088.11, 98.65% of payment value);
  payment_without_items 775 (0.78%; BRL 162,591.95, 1.02%);
  installment_interest 249 (0.25%; BRL 37,129.67, 0.23%; net +BRL 3,063.69 over items+freight);
  unexplained 50 (0.05%; BRL 15,813.72, 0.10%; net −BRL 196.72 — 11 pay more by BRL 2.36 total,
  39 pay less by BRL 199.08 total); voucher_overpayment 4 (BRL 248.67; net +BRL 4.09);
  items_without_payment 1 (items+freight BRL 143.46); no_items_no_payments 0.
  Installment/voucher categories are consistent explanations, not proven causes.
  Chart: `images/6c_reconciliation_exceptions.png`.
- **Cost to serve** (97,905 in-window orders with items, not canceled/unavailable): overall freight
  share 14.25% (BRL 2,234,177.06 of BRL 15,683,706.74). ≥100 orders: 24 of 27 states, 52 of 74 categories.
  Top states: MA 20.8% (732), RO 19.8% (246), AM 19.7% (147), PI 19.6% (489), SE 19.3% (342).
  Top categories: christmas_supplies 26.8% (127), signaling_and_security 23.2% (140),
  food_drink 22.9% (225), electronics 22.8% (2,542), furniture_living_room 20.7% (420).
  Overlap with top-5 late-rate states (AL, CE, MA, PI, SE): MA, PI, SE (3 of 5; all Northeast).
  RO and AM have high freight share but low late rates (2.9%, 2.8%). Across 24 states, Spearman
  ρ(freight share, late rate) = 0.28 (p = 0.189). SP lowest freight share 12.2%.
  Chart: `images/6c_freight_vs_late_by_state.png`.

## Dashboard data (Step 7 prep, `dashboard_data/`)
- Committed: small marts (`mart_cohort_retention`, `mart_cost_to_serve`, `mart_delivery_performance`)
  from `scripts/04_export_marts.py`, and summary tables `summary_kpis`, `summary_distance_bins`,
  `summary_review_timing`, `summary_reconciliation`, `summary_lanes` from
  `scripts/05_export_summaries.py` (all files < 30 KB).
- `scripts/05_export_summaries.py` recomputes every summary value from Snowflake and checks it
  against the numbers in this file (150 checks, all match on 2026-11-14).
- Not committed: order-level marts (10–20 MB each) in `dashboard_data/local/` (git-ignored).

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
- [x] Step 5 — analysis marts in `OLIST.ANALYSIS` + 46 dbt tests (45 pass, 1 expected warn)
- [x] Step 6 — Python analysis (6a delivery, 6b review impact, 6c retention/reconciliation/cost)
