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

## Rules
- **Explain each command before running it.**
- **Never commit credentials or raw data.** No passwords, private keys (`*.p8`, `*.pem`), `.env`
  files, or CSVs from `data/raw/`. Snowflake keys live in `~/.snowflake/`, dbt profiles in `~/.dbt/`.
- **Commit after each step.**
- **Never report findings that weren't computed.** Every number must come from code that was
  actually run against the data.

## Progress
- [x] Step 0 — repo, conda env, .gitignore, raw CSVs in `data/raw/`
