from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "clean_data" / "standardized_portfolio_holdings.csv"
DB = ROOT / "database" / "hidden_portfolio_risk.db"
OUT = ROOT / "outputs"
VALIDATION = ROOT / "validation"
SECTOR_DIR = ROOT / "sector_classification"

st.set_page_config(page_title="Hidden Portfolio Risk", page_icon="📊", layout="wide")

# Compact custom styling: no external services or API keys required.
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 1400px;}
[data-testid="stMetric"] {background: rgba(120,120,120,0.07); padding: 14px 16px; border-radius: 12px; border: 1px solid rgba(120,120,120,0.16);}
.hero {padding: 1.35rem 1.5rem; border-radius: 16px; background: linear-gradient(120deg, #102a43, #243b53); color: white; margin-bottom: 1rem;}
.hero h1 {color:white; margin:0; font-size:2.1rem;}
.hero p {color:#d9e6f2; margin:.45rem 0 0 0;}
.small-note {font-size: .85rem; opacity:.8;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    # The CSV is the reproducible source of truth; SQLite is included in the package
    # for demonstrating database storage and can be inspected independently.
    if not CLEAN.exists():
        raise FileNotFoundError(f"Cannot find {CLEAN}")
    df = pd.read_csv(CLEAN)
    df["disclosure_date"] = pd.to_datetime(df["disclosure_date"], errors="coerce")
    df["portfolio_weight_pct"] = pd.to_numeric(df["portfolio_weight_pct"], errors="coerce")
    for c in ["scheme_name", "security_name", "asset_type", "sector", "industry", "sector_mapping_status"]:
        if c in df:
            df[c] = df[c].fillna("Unknown").astype(str)
    return df

def equity_rows(df, scheme=None):
    x = df[df["asset_type"].str.casefold().eq("equity")].copy()
    if scheme:
        x = x[x["scheme_name"] == scheme]
    return x

def summarize_equity(df):
    rows = []
    for scheme, g in equity_rows(df).groupby("scheme_name", sort=True):
        weights = g["portfolio_weight_pct"].dropna().sort_values(ascending=False)
        rows.append({
            "Fund": scheme,
            "Equity records": int(len(g)),
            "Unique equity names": int(g["security_name"].nunique()),
            "Equity weight (% NAV)": round(g["portfolio_weight_pct"].sum(), 2),
            "Top 5 concentration (% NAV)": round(weights.head(5).sum(), 2),
            "Top 10 concentration (% NAV)": round(weights.head(10).sum(), 2),
            "Largest equity holding": g.loc[g["portfolio_weight_pct"].idxmax(), "security_name"] if len(g) else "—",
            "Largest holding weight (% NAV)": round(float(weights.iloc[0]), 2) if len(weights) else 0,
        })
    return pd.DataFrame(rows)

def chart_bar(data, x, y, title, y_label="% of scheme NAV"):
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.bar(data[x].astype(str), data[y])
    ax.set_title(title, loc="left", fontsize=13, pad=12)
    ax.set_ylabel(y_label)
    ax.tick_params(axis="x", rotation=22)
    ax.grid(axis="y", alpha=.25)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

try:
    data = load_data()
except Exception as e:
    st.error(f"Data could not be loaded: {e}")
    st.stop()

schemes = sorted(data["scheme_name"].dropna().unique().tolist())
summary = summarize_equity(data)
assets = data["asset_type"].value_counts().rename_axis("Asset type").reset_index(name="Rows")
disclosure_dates = data["disclosure_date"].dropna()
report_date = disclosure_dates.max().strftime("%d %b %Y") if len(disclosure_dates) else "Not recorded"

with st.sidebar:
    st.title("📊 Hidden Portfolio Risk")
    st.caption("Mutual fund portfolio analysis")
    page = st.radio("Navigate", [
        "Overview",
        "Fund Explorer",
        "Concentration & Diversification",
        "Risk Simulator",
        "Sector Exposure",
        "Data & Methodology",
    ])
    st.divider()
    st.caption("Data snapshot")
    st.write(f"**Reporting date:** {report_date}")
    st.write(f"**Funds:** {len(schemes)}")
    st.caption("Snapshot-based analysis — not live market data.")

st.markdown(f"""
<div class="hero">
  <h1>Hidden Portfolio Risk</h1>
  <p>Look beyond the number of holdings. Explore concentration, diversification and simple stress scenarios.</p>
  <p class="small-note">Five selected mutual fund schemes · Portfolio snapshot: {report_date}</p>
</div>
""", unsafe_allow_html=True)

if page == "Overview":
    st.subheader("Portfolio overview")
    st.write("Compare how portfolio weights are distributed across the five selected schemes. Equity concentration is measured as a percentage of the scheme's reported NAV, not re-scaled to 100% of equities.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Schemes analysed", len(schemes))
    c2.metric("Equity records", f"{len(equity_rows(data)):,}")
    c3.metric("Unique equity names", f"{equity_rows(data)['security_name'].nunique():,}")
    c4.metric("Disclosure date", report_date)
    st.markdown("#### Concentration snapshot")
    show = summary[["Fund", "Equity records", "Equity weight (% NAV)", "Top 5 concentration (% NAV)", "Top 10 concentration (% NAV)"]]
    st.dataframe(show, use_container_width=True, hide_index=True)
    chart_bar(summary, "Fund", "Top 5 concentration (% NAV)", "Top-five equity concentration by fund")
    st.info("Interpretation: a lower top-five concentration means the five largest equity positions account for a smaller share of scheme NAV. It does not, by itself, prove that a fund is safer.")
    st.download_button("Download summary CSV", summary.to_csv(index=False).encode("utf-8"), "fund_concentration_summary.csv", "text/csv")

elif page == "Fund Explorer":
    st.subheader("Fund Explorer")
    scheme = st.selectbox("Select a scheme", schemes)
    g_all = data[data["scheme_name"] == scheme].copy()
    g_eq = equity_rows(data, scheme).sort_values("portfolio_weight_pct", ascending=False)
    a, b, c, d = st.columns(4)
    a.metric("Equity records", f"{len(g_eq):,}")
    b.metric("Equity weight (% NAV)", f"{g_eq['portfolio_weight_pct'].sum():.2f}%")
    c.metric("Top 5 (% NAV)", f"{g_eq['portfolio_weight_pct'].head(5).sum():.2f}%")
    d.metric("Top 10 (% NAV)", f"{g_eq['portfolio_weight_pct'].head(10).sum():.2f}%")
    st.markdown("#### Largest equity positions")
    top_n = st.slider("Number of holdings to show", min_value=5, max_value=max(5, min(30, len(g_eq))), value=min(10, max(5, len(g_eq))))
    top = g_eq.head(top_n)[["security_name", "portfolio_weight_pct", "sector", "industry", "sector_mapping_status"]].copy()
    top.columns = ["Security", "Weight (% NAV)", "Working sector", "Industry / note", "Mapping status"]
    st.dataframe(top, use_container_width=True, hide_index=True)
    chart_bar(g_eq.head(top_n).rename(columns={"security_name":"Security","portfolio_weight_pct":"Weight"}), "Security", "Weight", f"Top {top_n} equity positions — {scheme}")
    st.markdown("#### All portfolio records")
    types = ["All"] + sorted(g_all["asset_type"].dropna().unique().tolist())
    chosen_type = st.selectbox("Filter by asset type", types)
    filtered = g_all if chosen_type == "All" else g_all[g_all["asset_type"] == chosen_type]
    st.dataframe(filtered[["security_name", "asset_type", "source_section", "portfolio_weight_pct", "shares_or_units", "sector", "sector_mapping_status"]], use_container_width=True, hide_index=True)
    st.download_button("Download selected fund records", filtered.to_csv(index=False).encode("utf-8"), f"{scheme.lower().replace(' ','_')}_records.csv", "text/csv")

elif page == "Concentration & Diversification":
    st.subheader("Concentration & Diversification")
    st.write("The diversification gap is a relative ranking indicator among these five schemes, not a universal risk score.")
    display = summary.copy()
    display["Holding-count rank"] = display["Equity records"].rank(method="min", ascending=False).astype(int)
    display["Top-five concentration rank"] = display["Top 5 concentration (% NAV)"].rank(method="min", ascending=True).astype(int)
    display["Diversification gap"] = display["Top-five concentration rank"] - display["Holding-count rank"]
    display = display.sort_values("Diversification gap")
    st.dataframe(display[["Fund", "Equity records", "Top 5 concentration (% NAV)", "Top 10 concentration (% NAV)", "Holding-count rank", "Top-five concentration rank", "Diversification gap"]], use_container_width=True, hide_index=True)
    chart_bar(summary, "Fund", "Top 10 concentration (% NAV)", "Top-ten equity concentration by fund")
    st.markdown("#### How to read the gap")
    st.markdown("- **Positive gap:** relative concentration rank is worse than holding-count rank.\n- **Negative gap:** relative concentration rank is better than holding-count rank.\n- **Zero:** the two ranks match.\n\nA high number of holdings does not guarantee diversification if a small number of positions dominate the portfolio or if holdings move together.")
    st.download_button("Download diversification comparison", display.to_csv(index=False).encode("utf-8"), "diversification_comparison.csv", "text/csv")

elif page == "Risk Simulator":
    st.subheader("Risk Simulator")
    st.write("Test a hypothetical price fall in one holding. This is a direct-weight sensitivity calculation, not a forecast.")
    scheme = st.selectbox("Choose a scheme", schemes, key="risk_scheme")
    holdings = equity_rows(data, scheme).sort_values("portfolio_weight_pct", ascending=False)
    holding_names = holdings["security_name"].tolist()
    holding = st.selectbox("Choose an equity holding", holding_names)
    row = holdings[holdings["security_name"] == holding].iloc[0]
    fall = st.slider("Assumed fall in this holding (%)", min_value=1, max_value=50, value=10)
    weight = float(row["portfolio_weight_pct"])
    impact = weight * fall / 100
    x1, x2, x3 = st.columns(3)
    x1.metric("Holding weight (% NAV)", f"{weight:.2f}%")
    x2.metric("Assumed holding decline", f"{fall}%")
    x3.metric("Direct portfolio impact", f"−{impact:.3f} percentage points")
    st.markdown(f"If **{holding}** falls by **{fall}%**, its direct estimated contribution to the scheme's return is approximately **−{impact:.3f} percentage points**, assuming the recorded weight and no offsetting effects.")
    scenario = pd.DataFrame({
        "Assumed holding decline (%)": [5, 10, 15, 20, 30, 50],
        "Estimated direct portfolio impact (percentage points)": [-weight * v / 100 for v in [5, 10, 15, 20, 30, 50]]
    })
    chart_bar(scenario, "Assumed holding decline (%)", "Estimated direct portfolio impact (percentage points)", "Sensitivity to a fall in the selected holding", "Percentage points (negative impact)")
    st.warning("Limitations: does not model derivatives/hedges, correlations, taxes, fees, trading, liquidity, rebalancing or changes in portfolio weights. This is an educational scenario, not investment advice.")
    st.download_button("Download scenario table", scenario.to_csv(index=False).encode("utf-8"), "holding_risk_scenario.csv", "text/csv")

elif page == "Sector Exposure":
    st.subheader("Sector Exposure")
    st.warning("Sector classifications are provisional. The current working map includes unclassified holdings and has not been fully verified against official company-level NSE records. Treat these charts as exploratory only.")
    sector_file = OUT / "sector_exposure_provisional.csv"
    if sector_file.exists():
        sectors = pd.read_csv(sector_file)
        fund = st.selectbox("Select scheme for sector view", schemes, key="sector_scheme")
        sg = sectors[sectors["scheme_name"] == fund].sort_values("sector_weight_pct_nav", ascending=False)
        st.caption("Weights shown as % of scheme NAV; unclassified positions are retained.")
        st.dataframe(sg[["nse_sector", "sector_weight_pct_nav", "equity_records", "unique_securities", "verification_status"]], use_container_width=True, hide_index=True)
        plot_data = sg.head(12).copy()
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.barh(plot_data["nse_sector"][::-1], plot_data["sector_weight_pct_nav"][::-1])
        ax.set_xlabel("% of scheme NAV")
        ax.set_title(f"Working sector map — {fund}", loc="left")
        ax.grid(axis="x", alpha=.25)
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        stress_file = OUT / "sector_stress_tests_provisional.csv"
        if stress_file.exists():
            st.markdown("#### Provisional sector stress tests")
            stress = pd.read_csv(stress_file)
            stress = stress[stress["scheme_name"] == fund]
            st.dataframe(stress, use_container_width=True, hide_index=True)
        st.download_button("Download sector exposure CSV", sg.to_csv(index=False).encode("utf-8"), f"{fund.lower().replace(' ','_')}_sector_exposure_provisional.csv", "text/csv")
    else:
        st.error("The provisional sector exposure output was not found in the project package.")

elif page == "Data & Methodology":
    st.subheader("Data & Methodology")
    st.markdown("#### Data provenance")
    st.write("This dashboard uses the September 2026 portfolio CSV snapshot included with the project. It does not fetch live holdings from external websites.")
    source_log = VALIDATION / "source_log.csv"
    if source_log.exists():
        st.markdown("**Recorded source log**")
        st.dataframe(pd.read_csv(source_log), use_container_width=True, hide_index=True)
    else:
        st.info("No source log file was found.")
    st.markdown("#### Validation and known caveats")
    validation_files = [
        ("Portfolio weight reconciliation", VALIDATION / "complete_portfolio_weight_reconciliation.csv"),
        ("Scheme-level validation", VALIDATION / "scheme_level_validation.csv"),
        ("Sector verification summary", VALIDATION / "official_sector_verification_summary.csv"),
    ]
    for title, file in validation_files:
        if file.exists():
            with st.expander(title):
                st.dataframe(pd.read_csv(file), use_container_width=True, hide_index=True)
    st.markdown("""
**Methodology**
- Standardised portfolio rows are loaded from the included CSV.
- Equity holdings are filtered by the recorded asset type.
- Top-five and top-ten concentration are calculated by summing the largest reported equity weights as a percentage of scheme NAV.
- Holding stress impact = holding weight × assumed fall percentage ÷ 100.
- Diversification gap = concentration rank − holding-count rank.
- No weights are automatically normalised, and unusual rows are not silently removed.

**Important limitations**
- Cross-check the CSV snapshots with official AMC monthly portfolio disclosures before final submission.
- Sector labels and sector stress scenarios are provisional.
- The ICICI Prudential Large Cap export totals about 102% when the Infosys futures row is included; this must be reconciled with the official disclosure and derivative treatment.
- UTI's supplied export does not provide AUM; no AUM has been inferred.
- Results are educational and do not constitute investment advice.
""")
    if CLEAN.exists():
        st.download_button("Download standardised source dataset", CLEAN.read_bytes(), "standardized_portfolio_holdings.csv", "text/csv")

st.divider()
st.caption("IPP project prototype · Snapshot analysis only · Validate official disclosures before final academic submission.")
