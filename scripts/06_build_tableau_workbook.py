"""Step 7: combine the committed dashboard_data/ CSVs into one Excel file for Tableau Public.

One tab per CSV, values unchanged. The only addition is a `state_name` column (full Brazilian
state name) on tabs with customer/seller states, so Tableau can geocode a filled map.
Reads the file back and verifies every tab equals its CSV.

Run from the repo root:  conda run -n olist python scripts/06_build_tableau_workbook.py
"""
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "dashboard_data"
OUT = REPO / "tableau" / "olist_dashboard_data.xlsx"

TABS = {
    "KPIs": "summary_kpis.csv",
    "Distance_Bins": "summary_distance_bins.csv",
    "Review_Timing": "summary_review_timing.csv",
    "Reconciliation": "summary_reconciliation.csv",
    "Lanes": "summary_lanes.csv",
    "Cohort_Retention": "mart_cohort_retention.csv",
    "Cost_to_Serve": "mart_cost_to_serve.csv",
    "Delivery_Performance": "mart_delivery_performance.csv",
}

STATES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
STATE_DIMS = {"customer_state", "seller_state"}


def add_state_name(df):
    """Full state name for rows whose dimension is a state; blank otherwise."""
    if "dimension" not in df.columns:
        return df
    df = df.copy()
    is_state = df["dimension"].isin(STATE_DIMS)
    df["state_name"] = df["group_value"].where(is_state).map(STATES)
    assert df.loc[is_state, "state_name"].notna().all(), "unmapped state code"
    return df


def main():
    OUT.parent.mkdir(exist_ok=True)
    frames = {tab: pd.read_csv(SRC / f) for tab, f in TABS.items()}
    frames = {tab: add_state_name(df) for tab, df in frames.items()}
    with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
        for tab, df in frames.items():
            df.to_excel(xl, sheet_name=tab, index=False)

    # Verify: every tab read back equals its CSV (plus the added state_name column).
    print(f"{'tab':<22}{'rows':>6}{'cols':>6}  check")
    for tab, f in TABS.items():
        back = pd.read_excel(OUT, sheet_name=tab)
        csv = pd.read_csv(SRC / f)
        orig_cols = list(csv.columns)
        pd.testing.assert_frame_equal(back[orig_cols], csv, check_dtype=False, check_exact=False,
                                      rtol=0, atol=1e-9)
        extra = [c for c in back.columns if c not in orig_cols]
        print(f"{tab:<22}{len(back):>6}{back.shape[1]:>6}  OK{'  (+' + ', '.join(extra) + ')' if extra else ''}")
    print(f"\nwrote {OUT.relative_to(REPO)} ({OUT.stat().st_size / 1e3:.1f} KB)")


if __name__ == "__main__":
    main()
