"""IPP Hidden Portfolio Risk — concentration analysis (beginner-friendly).

Run from this folder or any location:
    python python_code/03_final_analysis.py

All reported weights are % of scheme NAV as provided by the source export.
No weights are automatically normalised. Sector outputs remain PROVISIONAL until
each company-level mapping is verified against an official classification file.
"""
import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_FOLDER, "clean_data", "standardized_portfolio_holdings.csv")
MAP_FILE = os.path.join(BASE_FOLDER, "sector_classification", "sector_mapping_working.csv")
DB_FILE = os.path.join(BASE_FOLDER, "database", "hidden_portfolio_risk.db")
OUTPUT_FOLDER = os.path.join(BASE_FOLDER, "outputs")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def load_data(file_name):
    data = pd.read_csv(file_name)
    required = ["scheme_name", "security_name", "asset_type", "source_section", "portfolio_weight_pct"]
    for column in required:
        if column not in data.columns:
            raise ValueError("Required column is missing: " + column)
    data["portfolio_weight_pct"] = pd.to_numeric(data["portfolio_weight_pct"], errors="coerce")
    return data


def calculate_concentration(equity_data):
    """Calculate breadth and top-holding weights using reported NAV percentages."""
    results = []
    for scheme in sorted(equity_data["scheme_name"].dropna().unique()):
        fund = equity_data[equity_data["scheme_name"] == scheme].copy()
        fund = fund.dropna(subset=["portfolio_weight_pct"])
        fund = fund.sort_values("portfolio_weight_pct", ascending=False)
        weights = fund["portfolio_weight_pct"]
        results.append({
            "scheme_name": scheme,
            "equity_record_count": len(fund),
            "unique_equity_security_count": fund["security_name"].nunique(),
            "equity_weight_sum_pct_nav": round(float(weights.sum()), 4),
            "top_5_concentration_pct_nav": round(float(weights.head(5).sum()), 4),
            "top_10_concentration_pct_nav": round(float(weights.head(10).sum()), 4),
            "largest_equity_holding": fund.iloc[0]["security_name"] if len(fund) else "",
            "largest_equity_holding_weight_pct_nav": round(float(weights.iloc[0]), 4) if len(fund) else np.nan,
        })
    return pd.DataFrame(results)


def calculate_diversification_gap(concentration):
    """Compare count rank with concentration rank.

    Rank 1 on holding count = most holdings. Rank 1 on top-five concentration =
    lowest concentration. Gap = concentration rank - holding-count rank.
    Positive gap means concentration rank is worse than holding-count rank;
    negative gap means concentration rank is better. This is a relative rank
    comparison across this five-scheme sample, not a universal risk score.
    """
    result = concentration.copy()
    result["holding_count_rank"] = result["unique_equity_security_count"].rank(
        ascending=False, method="min").astype(int)
    result["top5_concentration_rank"] = result["top_5_concentration_pct_nav"].rank(
        ascending=True, method="min").astype(int)
    result["diversification_gap"] = result["top5_concentration_rank"] - result["holding_count_rank"]
    result["gap_interpretation"] = result["diversification_gap"].apply(
        lambda value: "Concentration rank worse than holding-count rank" if value > 0
        else ("Concentration rank better than holding-count rank" if value < 0
              else "Holding-count and concentration ranks align"))
    result["method_note"] = "Relative rank indicator within five selected schemes; not a standalone risk measure"
    return result


def calculate_section_weights(data):
    """Summarise all reported sections without forcing totals to 100%."""
    sections = data.groupby(["scheme_name", "source_section"], dropna=False).agg(
        records=("security_name", "size"),
        weight_sum_pct=("portfolio_weight_pct", "sum")
    ).reset_index()
    totals = data.groupby("scheme_name").agg(
        records=("security_name", "size"),
        all_reported_weight_sum_pct=("portfolio_weight_pct", "sum")
    ).reset_index()
    totals["difference_from_100_pct_points"] = (totals["all_reported_weight_sum_pct"] - 100).round(4)
    totals["validation_status"] = totals["difference_from_100_pct_points"].apply(
        lambda x: "Within ±0.10 percentage points; still cross-check source" if abs(x) <= 0.10
        else "REVIEW: outside ±0.10 percentage points; do not normalise")
    return sections, totals


def calculate_sector_exposure(equity_data, mapping):
    """Join the current mapping file; results explicitly remain provisional."""
    map_cols = ["security_name", "nse_sector", "nse_industry", "mapping_status", "classification_source"]
    mapping = mapping[[col for col in map_cols if col in mapping.columns]].drop_duplicates("security_name")
    merged = equity_data.merge(mapping, on="security_name", how="left")
    merged["nse_sector"] = merged["nse_sector"].fillna("Unclassified")
    merged["mapping_status"] = merged["mapping_status"].fillna("No mapping row")
    sector = merged.groupby(["scheme_name", "nse_sector"], as_index=False).agg(
        sector_weight_pct_nav=("portfolio_weight_pct", "sum"),
        equity_records=("security_name", "size"),
        unique_securities=("security_name", "nunique"),
        mapped_statuses=("mapping_status", lambda x: " | ".join(sorted(set(str(v) for v in x))))
    )
    sector["verification_status"] = "PROVISIONAL — not all company-level mappings verified against official NSE records"
    return sector.sort_values(["scheme_name", "sector_weight_pct_nav"], ascending=[True, False]), merged


def calculate_holding_scenarios(equity_data, declines=(10, 20)):
    rows = []
    for scheme in sorted(equity_data["scheme_name"].dropna().unique()):
        fund = equity_data[equity_data["scheme_name"] == scheme].dropna(subset=["portfolio_weight_pct"])
        if fund.empty:
            continue
        largest = fund.sort_values("portfolio_weight_pct", ascending=False).iloc[0]
        for decline in declines:
            rows.append({
                "scheme_name": scheme, "scenario_type": "Largest equity holding decline",
                "security_or_sector": largest["security_name"],
                "exposure_pct_nav": float(largest["portfolio_weight_pct"]),
                "assumed_decline_pct": decline,
                "estimated_direct_portfolio_impact_pct_points": round(float(largest["portfolio_weight_pct"]) * -decline / 100, 4),
                "status": "Hypothetical direct sensitivity; not a forecast"
            })
    return pd.DataFrame(rows)


def calculate_sector_scenarios(sector_exposure, declines=(10, 20)):
    """Stress the largest labelled sector for each fund; currently provisional."""
    rows = []
    for scheme in sorted(sector_exposure["scheme_name"].unique()):
        fund = sector_exposure[sector_exposure["scheme_name"] == scheme]
        # Unclassified is not a sector and must not be selected as a sector scenario.
        fund = fund[fund["nse_sector"] != "Unclassified"]
        if fund.empty:
            continue
        top = fund.sort_values("sector_weight_pct_nav", ascending=False).iloc[0]
        for decline in declines:
            rows.append({
                "scheme_name": scheme, "sector": top["nse_sector"],
                "sector_exposure_pct_nav": float(top["sector_weight_pct_nav"]),
                "assumed_sector_decline_pct": decline,
                "estimated_direct_portfolio_impact_pct_points": round(float(top["sector_weight_pct_nav"]) * -decline / 100, 4),
                "status": "PROVISIONAL — depends on sector mapping; hypothetical direct sensitivity only"
            })
    return pd.DataFrame(rows)


def save_to_sqlite(tables):
    with sqlite3.connect(DB_FILE) as connection:
        for table_name, frame in tables.items():
            frame.to_sql(table_name, connection, if_exists="replace", index=False)


def create_chart(concentration):
    chart_data = concentration.sort_values("top_5_concentration_pct_nav", ascending=True)
    plt.figure(figsize=(10, 6))
    plt.barh(chart_data["scheme_name"], chart_data["top_5_concentration_pct_nav"])
    plt.xlabel("Top-five equity holding weight (% of scheme NAV)")
    plt.ylabel("Scheme")
    plt.title("Top-Five Equity Holding Concentration — September 2026")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_FOLDER, "top_five_concentration.png"), dpi=150)
    plt.close()


