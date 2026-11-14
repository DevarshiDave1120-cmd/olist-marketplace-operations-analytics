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
