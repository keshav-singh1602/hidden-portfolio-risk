"""IPP Hidden Portfolio Risk - beginner-friendly concentration analysis.

Reads the standardised September 2026 holdings file and produces concentration
metrics and scenario calculations. Sector results are marked PROVISIONAL until
the sector mapping has been verified against official company-level data.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

BASE_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_FOLDER, "clean_data", "standardized_portfolio_holdings.csv")
DB_FILE = os.path.join(BASE_FOLDER, "database", "hidden_portfolio_risk.db")
OUTPUT_FOLDER = os.path.join(BASE_FOLDER, "outputs")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def load_data(file_name):
    """Load standardised records and check required columns."""
    data = pd.read_csv(file_name)
    required_columns = ["scheme_name", "security_name", "asset_type", "portfolio_weight_pct"]
    for column in required_columns:
        if column not in data.columns:
            raise ValueError("Required column is missing: " + column)
    data["portfolio_weight_pct"] = pd.to_numeric(data["portfolio_weight_pct"], errors="coerce")
    return data


def calculate_top_concentration(equity_data):
    """Calculate number of holdings and top-five/top-ten equity concentration."""
    results = []
    for scheme in sorted(equity_data["scheme_name"].dropna().unique()):
        one_scheme = equity_data[equity_data["scheme_name"] == scheme].copy()
        one_scheme = one_scheme.dropna(subset=["portfolio_weight_pct"])
        one_scheme = one_scheme.sort_values("portfolio_weight_pct", ascending=False)
        weights = one_scheme["portfolio_weight_pct"]
        results.append({
            "scheme_name": scheme,
            "equity_record_count": len(one_scheme),
            "unique_equity_security_count": one_scheme["security_name"].nunique(),
            "equity_weight_sum_pct": round(weights.sum(), 4),
            "top_5_concentration_pct": round(weights.head(5).sum(), 4),
            "top_10_concentration_pct": round(weights.head(10).sum(), 4),
            "largest_equity_holding": one_scheme.iloc[0]["security_name"] if len(one_scheme) else "",
            "largest_equity_holding_weight_pct": round(float(weights.iloc[0]), 4) if len(one_scheme) else np.nan,
            "sector_results_status": "Not final - verify sector mapping and source disclosure"
        })
    return pd.DataFrame(results)


def calculate_sector_exposure(equity_data):
    """Aggregate equity weights by mapped sector, but label unverified mappings."""
    required = ["sector", "sector_mapping_status"]
    for column in required:
        if column not in equity_data.columns:
            equity_data[column] = ""
    mapped = equity_data[equity_data["sector"].notna() & (equity_data["sector"].astype(str).str.strip() != "")].copy()
    if mapped.empty:
        return pd.DataFrame(columns=["scheme_name", "sector", "sector_weight_pct", "mapping_status", "interpretation_status"])
    sector_table = mapped.groupby(["scheme_name", "sector"], as_index=False)["portfolio_weight_pct"].sum()
    status = mapped.groupby(["scheme_name", "sector"])["sector_mapping_status"].apply(
        lambda values: "Verified" if all(values.astype(str).str.lower().str.contains("verified")) else "PROVISIONAL - verification required"
    ).reset_index(name="mapping_status")
    sector_table = sector_table.merge(status, on=["scheme_name", "sector"], how="left")
    sector_table = sector_table.rename(columns={"portfolio_weight_pct": "sector_weight_pct"})
    sector_table["interpretation_status"] = "Provisional only; do not use for final findings until mapping verified"
    return sector_table.sort_values(["scheme_name", "sector_weight_pct"], ascending=[True, False])


def calculate_scenarios(equity_data):
    """Estimate direct impact of hypothetical declines in each scheme's largest equity holding."""
    rows = []
    for scheme in sorted(equity_data["scheme_name"].dropna().unique()):
        one_scheme = equity_data[equity_data["scheme_name"] == scheme].dropna(subset=["portfolio_weight_pct"])
        if one_scheme.empty:
            continue
        largest = one_scheme.sort_values("portfolio_weight_pct", ascending=False).iloc[0]
        for decline in [10, 20]:
            impact = float(largest["portfolio_weight_pct"]) * (-decline / 100)
            rows.append({
                "scheme_name": scheme,
                "scenario_type": "Largest equity holding decline",
                "security_or_sector": largest["security_name"],
                "portfolio_weight_pct": round(float(largest["portfolio_weight_pct"]), 4),
                "assumed_decline_pct": decline,
                "estimated_direct_portfolio_impact_pct": round(impact, 4),
                "status": "Hypothetical sensitivity only; not a forecast"
            })
    return pd.DataFrame(rows)


def save_outputs(data, concentration, sector_exposure, scenarios):
    """Save result CSVs and store result tables in SQLite."""
    data.to_csv(os.path.join(OUTPUT_FOLDER, "analysis_input_snapshot.csv"), index=False)
    concentration.to_csv(os.path.join(OUTPUT_FOLDER, "holding_concentration_summary.csv"), index=False)
    sector_exposure.to_csv(os.path.join(OUTPUT_FOLDER, "sector_exposure_provisional.csv"), index=False)
    scenarios.to_csv(os.path.join(OUTPUT_FOLDER, "largest_holding_scenarios.csv"), index=False)
    with sqlite3.connect(DB_FILE) as connection:
        concentration.to_sql("holding_concentration_summary", connection, if_exists="replace", index=False)
        sector_exposure.to_sql("sector_exposure_provisional", connection, if_exists="replace", index=False)
        scenarios.to_sql("largest_holding_scenarios", connection, if_exists="replace", index=False)


def create_chart(concentration):
    """Create a simple chart of top-five equity concentration."""
    if concentration.empty:
        return
    chart_data = concentration.sort_values("top_5_concentration_pct", ascending=False)
    plt.figure(figsize=(10, 6))
    plt.barh(chart_data["scheme_name"], chart_data["top_5_concentration_pct"])
    plt.xlabel("Top five equity holdings (% of scheme NAV, as reported)")
    plt.ylabel("Mutual fund scheme")
    plt.title("Top-Five Equity Holding Concentration — September 2026")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_FOLDER, "top_five_concentration.png"), dpi=150)
    plt.close()


def main():
    all_data = load_data(DATA_FILE)
    equity_data = all_data[all_data["asset_type"].astype(str).str.lower() == "equity"].copy()
    concentration = calculate_top_concentration(equity_data)
    sector_exposure = calculate_sector_exposure(equity_data)
    scenarios = calculate_scenarios(equity_data)
    save_outputs(all_data, concentration, sector_exposure, scenarios)
    create_chart(concentration)
    print("Analysis complete. Outputs saved to:", OUTPUT_FOLDER)
    print("Equity records analysed:", len(equity_data))
    print("Important: sector mappings and source weights still require verification.")
    print(concentration.to_string(index=False))


if __name__ == "__main__":
    main()
