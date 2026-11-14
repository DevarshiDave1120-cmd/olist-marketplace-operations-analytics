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
